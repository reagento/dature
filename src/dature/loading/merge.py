"""Multi-source merge machinery.

Holds the merge core ``load_and_merge`` and its helpers. Single-source loading
lives directly on ``Loader._do_load_single`` in ``loader.py``.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass as stdlib_dataclass

from dature.errors import DatureConfigError, SourceLoadError
from dature.errors.extraction import handle_load_errors
from dature.load_report import LoadReport, _build_merge_report, attach_load_report
from dature.loading.context import coerce_flag_fields
from dature.loading.mask_config import resolve_mask_secrets
from dature.loading.merge_runtime import LoadCtx, MergeConfig, MergeStepEvent
from dature.loading.retort import transform_to_dataclass
from dature.loading.source_loading import enrich_skipped_errors
from dature.masking.detection import build_secret_paths
from dature.masking.masking import mask_json_value, mask_value
from dature.merging.deep_merge import deep_merge_last_wins
from dature.merging.field_group import FieldGroupContext, validate_field_groups
from dature.merging.predicate import ResolvedFieldGroup, build_field_group_paths, build_field_merge_map
from dature.protocols import DataclassInstance
from dature.report_types import FieldOrigin
from dature.sources.base import Source
from dature.strategies.source import resolve_source_strategy
from dature.type_aliases import JSONValue, TypeLoaderMap

logger = logging.getLogger("dature")


def _log_merge_step(
    *,
    event: MergeStepEvent,
    dataclass_name: str,
    strategy_label: str,
    secret_paths: frozenset[str],
) -> None:
    if isinstance(event.before, dict) and isinstance(event.source_data, dict):
        added = sorted(set(event.source_data.keys()) - set(event.before.keys()))
        overwritten = sorted(set(event.source_data.keys()) & set(event.before.keys()))
        logger.debug(
            "[%s] Merge step %d (strategy=%s): added=%s, overwritten=%s",
            dataclass_name,
            event.step_idx,
            strategy_label,
            added,
            overwritten,
        )
    masked = mask_json_value(event.after, secret_paths=secret_paths) if secret_paths else event.after
    logger.debug(
        "[%s] State after step %d: %s",
        dataclass_name,
        event.step_idx,
        masked,
    )


def _log_field_origins(
    *,
    dataclass_name: str,
    field_origins: tuple[FieldOrigin, ...],
    secret_paths: frozenset[str] = frozenset(),
) -> None:
    for origin in field_origins:
        if origin.key in secret_paths:
            masked = mask_value(str(origin.value))
            logger.debug(
                "[%s] Field '%s' = %r  <-- source %d (%s)",
                dataclass_name,
                origin.key,
                masked,
                origin.source_index,
                origin.source_file,
            )
        else:
            logger.debug(
                "[%s] Field '%s' = %r  <-- source %d (%s)",
                dataclass_name,
                origin.key,
                origin.value,
                origin.source_index,
                origin.source_file,
            )


def _collect_leaf_paths(data: JSONValue, prefix: str = "") -> list[str]:
    if not isinstance(data, dict):
        return [prefix] if prefix else []
    paths: list[str] = []
    for key, value in data.items():
        child_path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            paths.extend(_collect_leaf_paths(value, child_path))
        else:
            paths.append(child_path)
    return paths


def _validate_all_field_groups(
    *,
    raw_dicts: list[JSONValue],
    field_group_paths: tuple[ResolvedFieldGroup, ...],
    dataclass_name: str,
    source_reprs: tuple[str, ...],
) -> None:
    merged: JSONValue = {}
    field_origins: dict[str, int] = {}
    ctx = FieldGroupContext(
        source_reprs=source_reprs,
        field_origins=field_origins,
        dataclass_name=dataclass_name,
    )
    for step_idx, raw in enumerate(raw_dicts):
        validate_field_groups(
            base=merged,
            source=raw,
            field_group_paths=field_group_paths,
            source_index=step_idx,
            ctx=ctx,
        )
        for leaf_path in _collect_leaf_paths(raw):
            field_origins[leaf_path] = step_idx
        merged = deep_merge_last_wins(merged, raw)


def _collect_field_values(
    raw_dicts: list[JSONValue],
    field_path: str,
) -> list[JSONValue]:
    parts = field_path.split(".")
    values: list[JSONValue] = []
    for raw in raw_dicts:
        current: JSONValue = raw
        found = True
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                found = False
                break
            current = current[part]
        if found:
            values.append(current)
    return values


def _set_nested_value(
    data: JSONValue,
    field_path: str,
    value: JSONValue,
) -> JSONValue:
    if not isinstance(data, dict):
        return data
    parts = field_path.split(".")
    if len(parts) == 1:
        result = dict(data)
        result[parts[0]] = value
        return result
    key = parts[0]
    rest = ".".join(parts[1:])
    result = dict(data)
    if key in result:
        result[key] = _set_nested_value(result[key], rest, value)
    return result


@stdlib_dataclass(frozen=True, slots=True)
class _MergedData[T: DataclassInstance]:
    result: T
    merged_raw: JSONValue
    last_source: Source
    last_type_loaders: TypeLoaderMap | None


def load_and_merge[T: DataclassInstance](  # noqa: C901, PLR0912, PLR0915
    *,
    merge_meta: MergeConfig,
    schema: type[T],
    debug: bool = False,
    secret_paths: frozenset[str] | None = None,
) -> _MergedData[T]:
    mask_secrets = resolve_mask_secrets(load_level=merge_meta.mask_secrets)
    if secret_paths is None:
        computed: frozenset[str] = frozenset()
        if mask_secrets:
            extra_patterns = merge_meta.secret_field_names or ()
            computed = build_secret_paths(schema, extra_patterns=extra_patterns)
        secret_paths = computed

    strategy = resolve_source_strategy(
        merge_meta.strategy,
        dataclass_name=schema.__name__,
    )
    strategy_label = merge_meta.strategy if isinstance(merge_meta.strategy, str) else type(strategy).__name__

    on_merge_step: Callable[[MergeStepEvent], None] | None = None
    if logger.isEnabledFor(logging.DEBUG):

        def on_merge_step(event: MergeStepEvent) -> None:
            _log_merge_step(
                event=event,
                dataclass_name=schema.__name__,
                strategy_label=strategy_label,
                secret_paths=secret_paths,
            )

    field_merge_strategies = build_field_merge_map(
        merge_meta.field_merges,
        schema,
        dataclass_name=schema.__name__,
    )
    field_merge_paths = frozenset(field_merge_strategies.keys()) or None

    ctx = LoadCtx(
        merge_meta=merge_meta,
        schema=schema,
        dataclass_name=schema.__name__,
        field_merge_paths=field_merge_paths,
        secret_paths=secret_paths,
        mask_secrets=mask_secrets,
        on_merge_step=on_merge_step,
    )

    field_group_paths: tuple[ResolvedFieldGroup, ...] = ()
    if merge_meta.field_groups:
        field_group_paths = build_field_group_paths(merge_meta.field_groups, schema)

    merged = strategy(merge_meta.sources, ctx)

    # Validation runs after the strategy so that raw_dicts reflects exactly the
    # sources the strategy consumed — short-circuiting strategies like
    # SourceFirstFound contribute only one source, while SourceLastWins iterates
    # every source via ctx.merge anyway. SourceRaiseOnConflict performs its
    # conflict check internally during its own __call__.
    if field_group_paths:
        loaded_entries = ctx.build_report().source_entries
        source_reprs = tuple(repr(merge_meta.sources[entry.index]) for entry in loaded_entries)
        _validate_all_field_groups(
            raw_dicts=ctx.loaded_raw_dicts(),
            field_group_paths=field_group_paths,
            dataclass_name=schema.__name__,
            source_reprs=source_reprs,
        )

    if field_merge_strategies:
        loaded_for_fields = ctx.loaded_raw_dicts()
        for field_path, fs in field_merge_strategies.items():
            values = _collect_field_values(loaded_for_fields, field_path)
            if not values:
                continue
            aggregated = fs(values)
            merged = _set_nested_value(merged, field_path, aggregated)

    report = ctx.build_report()

    if report.last_source is None:
        if merge_meta.sources:
            msg = f"All {len(merge_meta.sources)} source(s) failed to load"
        else:
            msg = "load() requires at least one Source for merge"
        source_error = SourceLoadError(message=msg)
        raise DatureConfigError(schema.__name__, [source_error])
    last_source = report.last_source

    if secret_paths:
        masked_merged = mask_json_value(merged, secret_paths=secret_paths)
    else:
        masked_merged = merged
    logger.debug(
        "[%s] Merged result (strategy=%s, %d sources): %s",
        schema.__name__,
        strategy_label,
        len(report.raw_dicts),
        masked_merged,
    )

    frozen_entries = tuple(report.source_entries)
    field_origins = ctx.field_origins()

    _log_field_origins(
        dataclass_name=schema.__name__,
        field_origins=field_origins,
        secret_paths=secret_paths,
    )

    report_obj: LoadReport | None = None
    if debug:
        report_obj = _build_merge_report(
            dataclass_name=schema.__name__,
            strategy=strategy,
            source_entries=frozen_entries,
            field_origins=field_origins,
            merged_data=merged,
            secret_paths=secret_paths,
        )

    last_type_loaders = report.last_type_loaders
    last_error_ctx = report.source_ctxs[-1].error_ctx
    merged = coerce_flag_fields(merged, schema)
    try:
        result = handle_load_errors(
            func=lambda: transform_to_dataclass(
                last_source,
                merged,
                schema,
                resolved_type_loaders=last_type_loaders,
            ),
            ctx=last_error_ctx,
        )
    except DatureConfigError as exc:
        if report_obj is not None:
            attach_load_report(schema, report_obj)
        if report.skipped_fields:
            raise enrich_skipped_errors(exc, report.skipped_fields) from exc
        raise

    if report_obj is not None:
        attach_load_report(result, report_obj)

    return _MergedData(
        result=result,
        merged_raw=merged,
        last_source=last_source,
        last_type_loaders=report.last_type_loaders,
    )
