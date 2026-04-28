import logging
from collections.abc import Callable
from dataclasses import dataclass as stdlib_dataclass
from dataclasses import fields, is_dataclass
from typing import Any

from dature.errors import DatureConfigError, SourceLoadError
from dature.errors.formatter import enrich_skipped_errors, handle_load_errors
from dature.load_report import (
    FieldOrigin,
    LoadReport,
    SourceEntry,
    attach_load_report,
    get_load_report,
)
from dature.loading.common import resolve_mask_secrets
from dature.loading.context import (
    build_error_ctx,
    coerce_flag_fields,
    make_validating_post_init,
    merge_fields,
)
from dature.loading.merge_config import MergeConfig
from dature.loading.source_loading import resolve_type_loaders
from dature.masking.detection import build_secret_paths
from dature.masking.masking import mask_field_origins, mask_json_value, mask_source_entries, mask_value
from dature.merging.deep_merge import deep_merge_last_wins, raise_on_conflict
from dature.merging.field_group import FieldGroupContext, validate_field_groups
from dature.merging.predicate import ResolvedFieldGroup, build_field_group_paths, build_field_merge_map
from dature.protocols import DataclassInstance
from dature.sources.base import Source
from dature.sources.retort import (
    create_validating_retort,
    ensure_retort,
    transform_to_dataclass,
)
from dature.strategies.source import (
    LoadCtx,
    MergeStepEvent,
    SourceMergeStrategy,
    SourceRaiseOnConflict,
    resolve_source_strategy,
)
from dature.types import JSONValue, TypeLoaderMap

logger = logging.getLogger("dature")


def _collect_extra_secret_patterns(merge_meta: MergeConfig) -> tuple[str, ...]:
    return merge_meta.secret_field_names or ()


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


def _build_merge_report(
    *,
    dataclass_name: str,
    strategy: SourceMergeStrategy,
    source_entries: tuple[SourceEntry, ...],
    field_origins: tuple[FieldOrigin, ...],
    merged_data: JSONValue,
    secret_paths: frozenset[str] = frozenset(),
) -> LoadReport:
    if secret_paths:
        source_entries = mask_source_entries(source_entries, secret_paths=secret_paths)
        field_origins = mask_field_origins(field_origins, secret_paths=secret_paths)
        merged_data = mask_json_value(merged_data, secret_paths=secret_paths)

    return LoadReport(
        dataclass_name=dataclass_name,
        strategy=strategy,
        sources=source_entries,
        field_origins=field_origins,
        merged_data=merged_data,
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


def _load_and_merge[T: DataclassInstance](  # noqa: C901, PLR0912, PLR0915
    *,
    merge_meta: MergeConfig,
    schema: type[T],
    debug: bool = False,
) -> _MergedData[T]:
    secret_paths: frozenset[str] = frozenset()
    mask_secrets = resolve_mask_secrets(load_level=merge_meta.mask_secrets)
    if mask_secrets:
        extra_patterns = _collect_extra_secret_patterns(merge_meta)
        secret_paths = build_secret_paths(schema, extra_patterns=extra_patterns)

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

    ctx = LoadCtx(
        merge_meta=merge_meta,
        schema=schema,
        dataclass_name=schema.__name__,
        secret_paths=secret_paths,
        mask_secrets=mask_secrets,
        on_merge_step=on_merge_step,
    )

    field_merge_strategies = build_field_merge_map(
        merge_meta.field_merges,
        schema,
        dataclass_name=schema.__name__,
    )
    field_merge_paths = frozenset(field_merge_strategies.keys()) or None

    field_group_paths: tuple[ResolvedFieldGroup, ...] = ()
    if merge_meta.field_groups:
        field_group_paths = build_field_group_paths(merge_meta.field_groups, schema)

    # Pre-load all sources when we need to inspect raw data before the merge
    # happens (field-group validation, raise-on-conflict detection). The cache
    # in LoadCtx makes the strategy's own ctx.load() calls free.
    needs_pre_load = bool(field_group_paths) or isinstance(strategy, SourceRaiseOnConflict)
    if needs_pre_load:
        for src in merge_meta.sources:
            ctx.load(src)

    if field_group_paths:
        loaded_entries = ctx.build_report().source_entries
        source_reprs = tuple(repr(merge_meta.sources[entry.index]) for entry in loaded_entries)
        _validate_all_field_groups(
            raw_dicts=ctx.loaded_raw_dicts(),
            field_group_paths=field_group_paths,
            dataclass_name=schema.__name__,
            source_reprs=source_reprs,
        )

    if isinstance(strategy, SourceRaiseOnConflict):
        raise_on_conflict(
            ctx.loaded_raw_dicts(),
            ctx.loaded_source_ctxs(),
            schema.__name__,
            field_merge_paths=field_merge_paths,
        )

    merged = strategy(merge_meta.sources, ctx)

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


def merge_load_as_function[T: DataclassInstance](
    merge_meta: MergeConfig,
    schema: type[T],
    *,
    debug: bool,
) -> T:
    data = _load_and_merge(
        merge_meta=merge_meta,
        schema=schema,
        debug=debug,
    )

    last_type_loaders = data.last_type_loaders
    validating_retort = create_validating_retort(
        data.last_source,
        schema,
        resolved_type_loaders=last_type_loaders,
    )
    validation_loader = validating_retort.get_loader(schema)

    last_meta = data.last_source
    mask_secrets = resolve_mask_secrets(load_level=merge_meta.mask_secrets)
    secret_paths: frozenset[str] = frozenset()
    if mask_secrets:
        extra_patterns = _collect_extra_secret_patterns(merge_meta)
        secret_paths = build_secret_paths(schema, extra_patterns=extra_patterns)
    last_error_ctx = build_error_ctx(
        last_meta,
        schema.__name__,
        secret_paths=secret_paths,
        mask_secrets=mask_secrets,
    )
    try:
        handle_load_errors(
            func=lambda: validation_loader(data.merged_raw),
            ctx=last_error_ctx,
        )
    except DatureConfigError:
        if debug:
            report = get_load_report(data.result)
            if report is not None:
                attach_load_report(schema, report)
        raise

    return data.result


class _MergePatchContext:
    def __init__(
        self,
        *,
        merge_meta: MergeConfig,
        cls: type[DataclassInstance],
        cache: bool,
        debug: bool,
    ) -> None:
        self._prepare_sources(merge_meta=merge_meta, cls=cls)

        self.merge_meta = merge_meta
        self.cls = cls
        self.cache = cache
        self.debug = debug
        self.cached_data: DataclassInstance | None = None
        self.field_list = fields(cls)
        self.original_init = cls.__init__
        self.original_post_init = getattr(cls, "__post_init__", None)
        self.loading = False
        self.validating = False

        last_source = merge_meta.sources[-1]
        last_type_loaders = resolve_type_loaders(last_source, merge_meta.type_loaders)
        validating_retort = create_validating_retort(
            last_source,
            cls,
            resolved_type_loaders=last_type_loaders,
        )
        self.validation_loader: Callable[[JSONValue], DataclassInstance] = validating_retort.get_loader(cls)

        mask_secrets = resolve_mask_secrets(load_level=merge_meta.mask_secrets)
        self.secret_paths: frozenset[str] = frozenset()
        if mask_secrets:
            extra_patterns = _collect_extra_secret_patterns(merge_meta)
            self.secret_paths = build_secret_paths(cls, extra_patterns=extra_patterns)

        self.error_ctx = build_error_ctx(
            last_source,
            cls.__name__,
            secret_paths=self.secret_paths,
            mask_secrets=mask_secrets,
        )

    def _prepare_sources(
        self,
        *,
        merge_meta: MergeConfig,
        cls: type[DataclassInstance],
    ) -> None:
        for source in merge_meta.sources:
            type_loaders = resolve_type_loaders(source, merge_meta.type_loaders)
            ensure_retort(source, cls, resolved_type_loaders=type_loaders)


def _make_merge_new_init(ctx: _MergePatchContext) -> Callable[..., None]:
    def new_init(self: DataclassInstance, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        if ctx.loading:
            ctx.original_init(self, *args, **kwargs)
            return

        if ctx.cache and ctx.cached_data is not None:
            loaded_data = ctx.cached_data
        else:
            ctx.loading = True
            try:
                merged_data = _load_and_merge(
                    merge_meta=ctx.merge_meta,
                    schema=ctx.cls,
                    debug=ctx.debug,
                )
            finally:
                ctx.loading = False
            loaded_data = merged_data.result
            ctx.error_ctx = build_error_ctx(
                merged_data.last_source,
                ctx.cls.__name__,
                secret_paths=ctx.secret_paths,
                mask_secrets=ctx.error_ctx.mask_secrets,
            )
            if ctx.cache:
                ctx.cached_data = loaded_data

        complete_kwargs = merge_fields(loaded_data, ctx.field_list, args, kwargs)
        ctx.original_init(self, *args, **complete_kwargs)

        if ctx.debug:
            report = get_load_report(loaded_data)
            if report is not None:
                attach_load_report(self, report)

        if ctx.original_post_init is None:
            self.__post_init__()  # type: ignore[attr-defined]

    return new_init


def merge_make_decorator(
    merge_meta: MergeConfig,
    *,
    cache: bool,
    debug: bool,
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]:
    def decorator(cls: type[DataclassInstance]) -> type[DataclassInstance]:
        if not is_dataclass(cls):
            msg = f"{cls.__name__} must be a dataclass"
            raise TypeError(msg)

        ctx = _MergePatchContext(
            merge_meta=merge_meta,
            cls=cls,
            cache=cache,
            debug=debug,
        )
        cls.__init__ = _make_merge_new_init(ctx)  # type: ignore[method-assign]
        cls.__post_init__ = make_validating_post_init(ctx)  # type: ignore[attr-defined]
        return cls

    return decorator
