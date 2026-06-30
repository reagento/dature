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
from typing import cast

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
from dature.strategies.source import resolve_source_strategy
from dature.type_aliases import NOT_LOADED, JSONValue, TypeLoaderMap

logger = logging.getLogger("dature")


@dataclass(frozen=True, slots=True)
class _SingleData[T: DataclassInstance]:
    result: T
    error_ctx: ErrorContext


def load_single[T: DataclassInstance](  # noqa: C901, PLR0912, PLR0913, PLR0915
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
    loader_fn = retort_cache.root_retort(indexed, resolved_type_loaders=source_type_loaders).get_loader(schema)
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
        source_path = source.file_path_for_errors()
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

    raw_data = coerce_flag_fields(raw_data, schema)

    # Per-source field-pass validation: run field validators on the fields this source
    # provided (non-skip sources only — skip sources were already filtered at load time).
    # Single-source defers errors for merging with root-retort below (so one ExceptionGroup
    # covers both field + missing-field failures); multi-source raises per-source immediately.
    validated_field_names: set[str] = set()
    field_pass_errors: list[FieldLoadError] = []
    field_pass_result: dict[str, object] | None = None
    if not source.skip_field_if_invalid and retort_cache.has_validators(indexed):
        field_pass_result, field_pass_errors = run_source_field_pass(
            indexed=indexed,
            raw=raw_data,
            schema=schema,
            retort_cache=retort_cache,
            resolved_type_loaders=source_type_loaders,
            error_ctx=error_ctx,
            loaded_data=prepared.loaded_data,
        )
    elif source.skip_field_if_invalid and isinstance(raw_data, dict):
        # Skip-pass happened at load time; all remaining keys count as validated.
        validated_field_names.update(raw_data.keys())

    # Final construction: build the dataclass and fire schema-level root validators.
    # Root errors are merged with any field-pass errors: root paths have priority.
    try:
        constructed = handle_load_errors(
            func=lambda: loader_fn(raw_data),
            ctx=error_ctx,
            loaded_data=prepared.loaded_data,
        )
    except DatureConfigError as root_exc:
        combined_error = merge_root_and_field_errors(
            schema.__name__, cast("list[FieldLoadError]", list(root_exc.exceptions)), field_pass_errors
        )
        if report is not None:
            attach_load_report(schema, report)
        if skipped_fields:
            raise enrich_skipped_errors(combined_error, skipped_fields) from None
        raise combined_error from None

    if field_pass_result is not None:
        validated_field_names.update(name for name, value in field_pass_result.items() if value is not NOT_LOADED)

    # Field-pass errors without root errors: root_retort succeeded but validators failed.
    if field_pass_errors:
        field_pass_error = DatureConfigError(schema.__name__, field_pass_errors)
        if report is not None:
            attach_load_report(schema, report)
        if skipped_fields:
            raise enrich_skipped_errors(field_pass_error, skipped_fields) from None
        raise field_pass_error

    result: T = constructed

    # Default-field fallback: Annotated validators for fields no source provided (dataclass defaults).
    fallback_errors = compute_default_fallback_errors(schema, validated_field_names, result)
    if fallback_errors:
        fallback_error = DatureConfigError(schema.__name__, fallback_errors)
        if report is not None:
            attach_load_report(schema, report)
        raise fallback_error

    if report is not None:
        attach_load_report(result, report)

    return _SingleData(result=result, error_ctx=error_ctx)


@dataclass(frozen=True, slots=True)
class _MergedData[T: DataclassInstance]:
    result: T
    merged_raw: JSONValue
    last_loaded: IndexedSource
    last_type_loaders: TypeLoaderMap | None


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
    merged = coerce_flag_fields(merged, schema)

    # Per-source field-pass validation: for each non-skip source that has field validators,
    # run field_pass(skip=False) on the source's OWN raw dict.  Fields absent from that dict
    # remain NOT_LOADED and their validators do not fire — no "incomplete state" problem.
    # Collect the set of field names that were validated by at least one source.
    validated_field_names: set[str] = set()
    for source_indexed, raw_dict, source_ctx in ctx.loaded_sources():
        source = source_indexed.source
        if source.skip_field_if_invalid:
            # Drop-pass already happened at load time (apply_skip_invalid).
            # All non-NOT_LOADED leaf names in the cleaned dict count as validated.
            if isinstance(raw_dict, dict):
                validated_field_names.update(raw_dict.keys())
            continue
        if not retort_cache.has_validators(source_indexed):
            continue
        source_type_loaders = resolve_type_loaders(source, merge_meta.type_loaders)
        field_pass_result, field_pass_errors = run_source_field_pass(
            indexed=source_indexed,
            raw=raw_dict,
            schema=schema,
            retort_cache=retort_cache,
            resolved_type_loaders=source_type_loaders,
            error_ctx=source_ctx.error_ctx,
            loaded_data=source_ctx.loaded_data,
        )
        if field_pass_errors:
            # Multi-source: raise per-source immediately (different from single-source,
            # which defers to merge field errors with root-retort errors).
            field_pass_error = DatureConfigError(schema.__name__, field_pass_errors)
            if report_obj is not None:
                attach_load_report(schema, report_obj)
            if report.skipped_fields:
                raise enrich_skipped_errors(field_pass_error, report.skipped_fields) from None
            raise field_pass_error
        if field_pass_result is not None:
            validated_field_names.update(name for name, value in field_pass_result.items() if value is not NOT_LOADED)

    # Final construction: build the dataclass and fire schema-level root validators.
    final_retort = retort_cache.root_retort(last_loaded, resolved_type_loaders=last_type_loaders)
    try:
        result = handle_load_errors(
            func=lambda: final_retort.load(merged, schema),
            ctx=last_error_ctx,
            loaded_data=last_source_ctx.loaded_data,
        )
    except DatureConfigError as exc:
        if report_obj is not None:
            attach_load_report(schema, report_obj)
        if report.skipped_fields:
            raise enrich_skipped_errors(exc, report.skipped_fields) from None
        raise

    # Default-field fallback: Annotated validators for fields no source provided (dataclass defaults).
    fallback_errors = compute_default_fallback_errors(schema, validated_field_names, result)
    if fallback_errors:
        fallback_error = DatureConfigError(schema.__name__, fallback_errors)
        if report_obj is not None:
            attach_load_report(schema, report_obj)
        raise fallback_error

    if report_obj is not None:
        attach_load_report(result, report_obj)

    return _MergedData(
        result=result,
        merged_raw=merged,
        last_loaded=last_loaded,
        last_type_loaders=report.last_type_loaders,
    )
