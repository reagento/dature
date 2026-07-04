"""Single-source and multi-source load orchestration.

``load_single`` handles one source; ``load_and_merge`` handles multiple sources.
Their documented single/multi asymmetry is intentional and visible here side-by-side:
single-source defers field-pass errors and merges them with root-retort errors (one
ExceptionGroup covers both validator and missing-field failures), while multi-source raises
per-source immediately so the caller knows exactly which source failed.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Never, cast

from adaptix import Retort

from dature.errors import DatureConfigError, FieldLoadError, SourceLoadError
from dature.errors.extraction import handle_load_errors
from dature.errors.location import ErrorContext, SkippedFieldSource
from dature.loading.context import build_error_ctx, coerce_flag_fields
from dature.loading.field_pass import (
    compute_default_fallback_errors,
    merge_root_and_field_errors,
    run_source_field_pass,
)
from dature.loading.load_logging import log_field_origins, log_merge_step, log_single_source_load
from dature.loading.mask_config import resolve_mask_secrets
from dature.loading.merge_runtime import LoadCtx, MergeConfig, MergeStepEvent, resolve_type_loaders
from dature.loading.retort import RetortCache
from dature.loading.source_loading import enrich_skipped_errors, prepare_loaded_source
from dature.masking.detection import build_secret_paths
from dature.masking.masking import mask_json_value
from dature.merging.field_group import validate_all_field_groups
from dature.merging.predicate import ResolvedFieldGroup, build_field_group_paths, build_field_merge_map
from dature.nested_dict import collect_field_values, set_nested_value
from dature.protocols import DataclassInstance
from dature.report import LoadReport, _build_merge_report, _build_single_source_report, attach_load_report
from dature.sources.base import IndexedSource
from dature.sources.protocol import FileSourceProtocol
from dature.strategies.source import resolve_source_strategy
from dature.type_aliases import NOT_LOADED, JSONValue, TypeLoaderMap

logger = logging.getLogger("dature")


@dataclass(frozen=True, slots=True)
class _SingleData[T: DataclassInstance]:
    result: T
    error_ctx: ErrorContext


def load_single[T: DataclassInstance](  # noqa: PLR0913
    *,
    indexed: IndexedSource,
    schema: type[T],
    retort_cache: RetortCache,
    type_loaders: TypeLoaderMap | None,
    secret_paths: frozenset[str],
    mask_secrets: bool | None,
    probe_retort: Retort | None,
    debug: bool,
) -> _SingleData[T]:
    """Load a single source into *schema* and return the result with its final error context.

    Parallel to ``load_and_merge`` for multi-source loading.  The key asymmetry: single-source
    defers field-pass errors and merges them with root-retort errors (so coercion failures and
    validator failures are reported together in one ExceptionGroup); multi-source raises per-source
    immediately.
    """
    source = indexed.source
    source_type_loaders = resolve_type_loaders(source, type_loaders)
    resolved_mask_secrets = resolve_mask_secrets(load_level=mask_secrets)
    error_ctx = build_error_ctx(source, schema.__name__, secret_paths=secret_paths, mask_secrets=resolved_mask_secrets)

    load_result = handle_load_errors(func=source.load_raw, ctx=error_ctx)
    prepared = prepare_loaded_source(
        load_result=load_result,
        source=source,
        schema=schema,
        dataclass_name=schema.__name__,
        base_error_ctx=error_ctx,
        skip_value=source.skip_field_if_invalid,
        secret_paths=secret_paths,
        mask_secrets=resolved_mask_secrets,
        log_prefix=f"[{schema.__name__}]",
        probe_retort=probe_retort,
    )
    raw_data = prepared.raw_data
    error_ctx = prepared.error_ctx  # may differ from pre-load ctx if nested_conflicts
    skipped_fields: dict[str, list[SkippedFieldSource]] = {}
    for path, skipped_source in prepared.skipped:
        skipped_fields.setdefault(path, []).append(skipped_source)

    format_name = source.format_name
    report: LoadReport | None = None
    if debug:
        source_path = source.file_path_for_errors() if isinstance(source, FileSourceProtocol) else None
        report_file_path = str(source_path) if source_path is not None else source.display_name()
        report = _build_single_source_report(
            dataclass_name=schema.__name__,
            loader_type=format_name,
            file_path=report_file_path,
            raw_data=raw_data,
            secret_paths=secret_paths,
        )

    log_single_source_load(
        dataclass_name=schema.__name__,
        loader_type=format_name,
        file_path=source.display_name(),
        data=raw_data if isinstance(raw_data, dict) else {},
        secret_paths=secret_paths,
    )

    entry = _FieldPassEntry(
        indexed=indexed,
        own_raw=raw_data,
        resolved_type_loaders=source_type_loaders,
        error_ctx=error_ctx,
        loaded_data=prepared.loaded_data,
    )
    finalize_ctx = _FinalizeCtx(
        merged=raw_data,
        last_loaded=indexed,
        last_type_loaders=source_type_loaders,
        last_error_ctx=error_ctx,
        last_loaded_data=prepared.loaded_data,
        error_mode="defer",
        report_obj=report,
        skipped_fields=skipped_fields,
    )
    result = _finalize_load(
        ctx=finalize_ctx,
        field_pass_entries=[entry],
        schema=schema,
        retort_cache=retort_cache,
    )
    return _SingleData(result=result, error_ctx=error_ctx)


@dataclass(frozen=True, slots=True)
class _MergedData[T: DataclassInstance]:
    result: T
    merged_raw: JSONValue
    last_loaded: IndexedSource
    last_type_loaders: TypeLoaderMap | None


@dataclass(frozen=True, slots=True)
class _FieldPassEntry:
    """Per-source inputs for the shared finalization tail."""

    indexed: IndexedSource
    own_raw: JSONValue
    resolved_type_loaders: TypeLoaderMap | None
    error_ctx: ErrorContext
    loaded_data: JSONValue


@dataclass(frozen=True, slots=True)
class _FinalizeCtx:
    """Bundled parameters for _finalize_load that describe the merge result and root-construction inputs."""

    merged: JSONValue
    last_loaded: IndexedSource
    last_type_loaders: TypeLoaderMap | None
    last_error_ctx: ErrorContext
    last_loaded_data: JSONValue
    error_mode: Literal["defer", "immediate"]
    report_obj: LoadReport | None
    skipped_fields: dict[str, list[SkippedFieldSource]]


def _raise_config_error(
    exc: DatureConfigError,
    schema: type,
    report_obj: LoadReport | None,
    skipped_fields: dict[str, list[SkippedFieldSource]],
    *,
    from_none: bool = False,
) -> Never:
    """Attach the load report and re-raise *exc*, optionally suppressing the exception chain."""
    if report_obj is not None:
        attach_load_report(schema, report_obj)
    if skipped_fields:
        raise enrich_skipped_errors(exc, skipped_fields) from None
    if from_none:
        raise exc from None
    raise exc


def _run_field_passes(
    field_pass_entries: list[_FieldPassEntry],
    schema: type[DataclassInstance],
    retort_cache: RetortCache,
    ctx: _FinalizeCtx,
) -> tuple[set[str], list[FieldLoadError]]:
    """Run per-source field-pass validators; return (validated_names, deferred_errors).

    In ``"immediate"`` mode raises directly on the first source that fails.
    In ``"defer"`` mode accumulates errors for later merging with root-construction errors.
    """
    validated_field_names: set[str] = set()
    deferred_field_errors: list[FieldLoadError] = []

    for entry in field_pass_entries:
        source = entry.indexed.source
        own_raw = coerce_flag_fields(entry.own_raw, schema)
        if source.skip_field_if_invalid:
            if isinstance(own_raw, dict):
                validated_field_names.update(own_raw.keys())
            continue
        if not retort_cache.has_validators(entry.indexed):
            continue
        field_pass_result, field_pass_errors = run_source_field_pass(
            indexed=entry.indexed,
            raw=own_raw,
            schema=schema,
            retort_cache=retort_cache,
            resolved_type_loaders=entry.resolved_type_loaders,
            error_ctx=entry.error_ctx,
            loaded_data=entry.loaded_data,
        )
        if field_pass_errors:
            if ctx.error_mode == "immediate":
                field_pass_error = DatureConfigError(schema.__name__, field_pass_errors)
                if ctx.report_obj is not None:
                    attach_load_report(schema, ctx.report_obj)
                if ctx.skipped_fields:
                    raise enrich_skipped_errors(field_pass_error, ctx.skipped_fields) from None
                raise field_pass_error
            deferred_field_errors.extend(field_pass_errors)
        if field_pass_result is not None:
            validated_field_names.update(name for name, value in field_pass_result.items() if value is not NOT_LOADED)

    return validated_field_names, deferred_field_errors


def _finalize_load[T: DataclassInstance](
    *,
    ctx: _FinalizeCtx,
    field_pass_entries: list[_FieldPassEntry],
    schema: type[T],
    retort_cache: RetortCache,
) -> T:
    """Shared finalization tail: coerce → per-source field-pass → construct → fallback.

    *ctx.error_mode* encodes the intentional single/multi asymmetry (D2):
    - ``"defer"`` (single-source): field-pass errors are accumulated and merged
      with root-construction errors so all failures surface in one ExceptionGroup.
    - ``"immediate"`` (multi-source): field-pass errors are raised per-source
      immediately, before root construction runs.
    """
    validated_field_names, deferred_field_errors = _run_field_passes(field_pass_entries, schema, retort_cache, ctx)

    merged = coerce_flag_fields(ctx.merged, schema)
    final_retort = retort_cache.root_retort(ctx.last_loaded, resolved_type_loaders=ctx.last_type_loaders)
    try:
        result: T = handle_load_errors(
            func=lambda: final_retort.load(merged, schema),
            ctx=ctx.last_error_ctx,
            loaded_data=ctx.last_loaded_data,
        )
    except DatureConfigError as root_exc:
        if ctx.error_mode == "defer":
            combined = merge_root_and_field_errors(
                schema.__name__,
                cast("list[FieldLoadError]", list(root_exc.exceptions)),
                deferred_field_errors,
            )
            _raise_config_error(combined, schema, ctx.report_obj, ctx.skipped_fields, from_none=True)
        if ctx.report_obj is not None:
            attach_load_report(schema, ctx.report_obj)
        if ctx.skipped_fields:
            raise enrich_skipped_errors(root_exc, ctx.skipped_fields) from None
        raise

    if deferred_field_errors:
        field_pass_error = DatureConfigError(schema.__name__, deferred_field_errors)
        _raise_config_error(field_pass_error, schema, ctx.report_obj, ctx.skipped_fields)

    fallback_errors = compute_default_fallback_errors(schema, validated_field_names, result)
    if fallback_errors:
        fallback_error = DatureConfigError(schema.__name__, fallback_errors)
        if ctx.report_obj is not None:
            attach_load_report(schema, ctx.report_obj)
        raise fallback_error

    if ctx.report_obj is not None:
        attach_load_report(result, ctx.report_obj)

    return result


def load_and_merge[T: DataclassInstance](  # noqa: C901, PLR0912, PLR0915
    *,
    merge_meta: MergeConfig,
    schema: type[T],
    retort_cache: RetortCache,
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
            log_merge_step(
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
        retort_cache=retort_cache,
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
        validate_all_field_groups(
            raw_dicts=ctx.loaded_raw_dicts(),
            field_group_paths=field_group_paths,
            dataclass_name=schema.__name__,
            source_reprs=source_reprs,
        )

    if field_merge_strategies:
        loaded_for_fields = ctx.loaded_raw_dicts()
        for field_path, field_strategy in field_merge_strategies.items():
            values = collect_field_values(loaded_for_fields, field_path)
            if not values:
                continue
            aggregated = field_strategy(values)
            merged = set_nested_value(merged, field_path, aggregated)

    report = ctx.build_report()

    if report.last_loaded is None:
        if merge_meta.sources:
            msg = f"All {len(merge_meta.sources)} source(s) failed to load"
        else:
            msg = "load() requires at least one Source for merge"
        source_error = SourceLoadError(message=msg)
        raise DatureConfigError(schema.__name__, [source_error])
    last_loaded = report.last_loaded

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

    log_field_origins(
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
    last_source_ctx = report.source_ctxs[-1]
    last_error_ctx = last_source_ctx.error_ctx

    field_pass_entries = [
        _FieldPassEntry(
            indexed=src_indexed,
            own_raw=raw_dict,
            resolved_type_loaders=resolve_type_loaders(src_indexed.source, merge_meta.type_loaders),
            error_ctx=source_ctx.error_ctx,
            loaded_data=source_ctx.loaded_data,
        )
        for src_indexed, raw_dict, source_ctx in ctx.loaded_sources()
    ]
    finalize_ctx = _FinalizeCtx(
        merged=merged,
        last_loaded=last_loaded,
        last_type_loaders=last_type_loaders,
        last_error_ctx=last_error_ctx,
        last_loaded_data=last_source_ctx.loaded_data,
        error_mode="immediate",
        report_obj=report_obj,
        skipped_fields=report.skipped_fields,
    )
    result = _finalize_load(
        ctx=finalize_ctx,
        field_pass_entries=field_pass_entries,
        schema=schema,
        retort_cache=retort_cache,
    )
    return _MergedData(
        result=result,
        merged_raw=merged,
        last_loaded=last_loaded,
        last_type_loaders=last_type_loaders,
    )
