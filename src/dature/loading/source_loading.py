import logging
from dataclasses import dataclass
from functools import partial

from dature.config import config
from dature.errors import DatureConfigError, SourceLoadError, SourceLocation
from dature.errors.formatter import handle_load_errors
from dature.errors.location import ErrorContext, read_file_content
from dature.field_path import FieldPath
from dature.load_report import SourceEntry
from dature.loading.context import apply_skip_invalid, build_error_ctx
from dature.loading.merge_config import MergeConfig
from dature.masking.masking import mask_json_value
from dature.merging.strategy import MergeStrategyEnum
from dature.protocols import DataclassInstance
from dature.skip_field_provider import FilterResult
from dature.sources.base import FlatKeySource, Source
from dature.types import (
    ExpandEnvVarsMode,
    JSONValue,
    LoadRawResult,
    NestedResolve,
    NestedResolveStrategy,
    TypeLoaderMap,
)

logger = logging.getLogger("dature")


def load_source_raw(source: Source, resolved: "ResolvedSourceParams") -> LoadRawResult:
    if isinstance(source, FlatKeySource):
        return source.load_raw(
            resolved_expand=resolved.expand_env_vars,
            resolved_nested_strategy=resolved.nested_resolve_strategy,
            resolved_nested_resolve=resolved.nested_resolve,
        )
    return source.load_raw(resolved_expand=resolved.expand_env_vars)


@dataclass(frozen=True, slots=True)
class ResolvedSourceParams:
    expand_env_vars: ExpandEnvVarsMode
    type_loaders: TypeLoaderMap | None
    nested_resolve_strategy: NestedResolveStrategy
    nested_resolve: NestedResolve | None


def resolve_source_params(
    source: Source,
    *,
    load_expand_env_vars: ExpandEnvVarsMode | None = None,
    load_type_loaders: TypeLoaderMap | None = None,
    load_nested_resolve_strategy: NestedResolveStrategy | None = None,
    load_nested_resolve: NestedResolve | None = None,
) -> ResolvedSourceParams:
    resolved_expand: ExpandEnvVarsMode = "default"
    if source.expand_env_vars is not None:
        resolved_expand = source.expand_env_vars
    elif load_expand_env_vars is not None:
        resolved_expand = load_expand_env_vars

    source_loaders = source.type_loaders or {}
    load_loaders = load_type_loaders or {}
    config_loaders = config.type_loaders or {}
    merged_loaders = {**config_loaders, **load_loaders, **source_loaders}
    resolved_type_loaders = merged_loaders or None

    resolved_nested_strategy: NestedResolveStrategy = config.loading.nested_resolve_strategy
    if isinstance(source, FlatKeySource) and source.nested_resolve_strategy != "flat":
        resolved_nested_strategy = source.nested_resolve_strategy
    elif load_nested_resolve_strategy is not None:
        resolved_nested_strategy = load_nested_resolve_strategy

    resolved_nested_resolve: NestedResolve | None = None
    if isinstance(source, FlatKeySource) and source.nested_resolve is not None:
        resolved_nested_resolve = source.nested_resolve
    elif load_nested_resolve is not None:
        resolved_nested_resolve = load_nested_resolve

    return ResolvedSourceParams(
        expand_env_vars=resolved_expand,
        type_loaders=resolved_type_loaders,
        nested_resolve_strategy=resolved_nested_strategy,
        nested_resolve=resolved_nested_resolve,
    )


def should_skip_broken(source: Source, merge_meta: MergeConfig) -> bool:
    if source.skip_if_broken is not None:
        if source.file_display() is None:
            logger.warning(
                "skip_if_broken has no effect on environment variable sources — they cannot be broken",
            )
        return source.skip_if_broken
    return merge_meta.skip_broken_sources


def resolve_expand_env_vars(source: Source, merge_meta: MergeConfig) -> ExpandEnvVarsMode:
    if source.expand_env_vars is not None:
        return source.expand_env_vars
    return merge_meta.expand_env_vars


def resolve_skip_invalid(
    source: Source,
    merge_meta: MergeConfig,
) -> bool | tuple[FieldPath, ...]:
    if source.skip_if_invalid is not None:
        return source.skip_if_invalid
    return merge_meta.skip_invalid_fields


def resolve_mask_secrets(source: Source, merge_meta: MergeConfig) -> bool:
    if source.mask_secrets is not None:
        return source.mask_secrets
    if merge_meta.mask_secrets is not None:
        return merge_meta.mask_secrets
    return config.masking.mask_secrets


def resolve_secret_field_names(source: Source, merge_meta: MergeConfig) -> tuple[str, ...]:
    source_names = source.secret_field_names or ()
    merge_names = merge_meta.secret_field_names or ()
    return source_names + merge_names


def apply_merge_skip_invalid(
    *,
    raw: JSONValue,
    source: Source,
    merge_meta: MergeConfig,
    schema: type[DataclassInstance],
    source_index: int,
) -> FilterResult:
    skip_value = resolve_skip_invalid(source, merge_meta)
    if not skip_value:
        return FilterResult(cleaned_dict=raw, skipped_paths=[])

    return apply_skip_invalid(
        raw=raw,
        skip_if_invalid=skip_value,
        source=source,
        schema=schema,
        log_prefix=f"[{schema.__name__}] Source {source_index}:",
    )


@dataclass(frozen=True, slots=True)
class SourceContext:
    error_ctx: ErrorContext
    file_content: str | None


@dataclass(frozen=True, slots=True)
class SkippedFieldSource:
    source: Source
    error_ctx: ErrorContext
    file_content: str | None


@dataclass(frozen=True, slots=True)
class LoadedSources:
    raw_dicts: list[JSONValue]
    source_ctxs: list[SourceContext]
    source_entries: list[SourceEntry]
    last_source: Source
    last_resolved: ResolvedSourceParams
    skipped_fields: dict[str, list[SkippedFieldSource]]


def load_sources(  # noqa: C901, PLR0912, PLR0915
    *,
    merge_meta: MergeConfig,
    dataclass_name: str,
    schema: type[DataclassInstance],
    secret_paths: frozenset[str] = frozenset(),
    mask_secrets: bool = False,
) -> LoadedSources:
    raw_dicts: list[JSONValue] = []
    source_ctxs: list[SourceContext] = []
    source_entries: list[SourceEntry] = []
    last_source: Source | None = None
    last_resolved: ResolvedSourceParams | None = None
    skipped_fields: dict[str, list[SkippedFieldSource]] = {}

    for i, source_item in enumerate(merge_meta.sources):
        resolved = resolve_source_params(
            source_item,
            load_expand_env_vars=merge_meta.expand_env_vars,
            load_type_loaders=merge_meta.type_loaders,
            load_nested_resolve_strategy=merge_meta.nested_resolve_strategy,
            load_nested_resolve=merge_meta.nested_resolve,
        )
        error_ctx = build_error_ctx(source_item, dataclass_name, secret_paths=secret_paths, mask_secrets=mask_secrets)

        try:
            load_result = handle_load_errors(
                func=partial(load_source_raw, source_item, resolved),
                ctx=error_ctx,
            )
        except (DatureConfigError, FileNotFoundError):
            if merge_meta.strategy != MergeStrategyEnum.FIRST_FOUND and not should_skip_broken(source_item, merge_meta):
                raise
            logger.warning(
                "[%s] Source %d skipped (broken): file=%s",
                dataclass_name,
                i,
                source_item.file_display() or "<env>",
            )
            continue
        except Exception as exc:
            if merge_meta.strategy != MergeStrategyEnum.FIRST_FOUND and not should_skip_broken(source_item, merge_meta):
                location = SourceLocation(
                    location_label=type(source_item).location_label,
                    file_path=error_ctx.file_path,
                    line_range=None,
                    line_content=None,
                    env_var_name=None,
                )
                source_error = SourceLoadError(
                    message=str(exc),
                    location=location,
                )
                raise DatureConfigError(dataclass_name, [source_error]) from exc
            logger.warning(
                "[%s] Source %d skipped (broken): file=%s",
                dataclass_name,
                i,
                source_item.file_display() or "<env>",
            )
            continue

        raw = load_result.data
        if load_result.nested_conflicts:
            error_ctx = build_error_ctx(
                source_item,
                dataclass_name,
                secret_paths=secret_paths,
                mask_secrets=mask_secrets,
                nested_conflicts=load_result.nested_conflicts,
            )

        file_content = read_file_content(error_ctx.file_path)

        filter_result = apply_merge_skip_invalid(
            raw=raw,
            source=source_item,
            merge_meta=merge_meta,
            schema=schema,
            source_index=i,
        )

        for path in filter_result.skipped_paths:
            skipped_fields.setdefault(path, []).append(
                SkippedFieldSource(source=source_item, error_ctx=error_ctx, file_content=file_content),
            )

        raw = filter_result.cleaned_dict
        raw_dicts.append(raw)

        format_name = type(source_item).format_name

        logger.debug(
            "[%s] Source %d loaded: loader=%s, file=%s, keys=%s",
            dataclass_name,
            i,
            format_name,
            source_item.file_display() or "<env>",
            sorted(raw.keys()) if isinstance(raw, dict) else "<non-dict>",
        )
        if secret_paths:
            masked_raw = mask_json_value(raw, secret_paths=secret_paths)
        else:
            masked_raw = raw
        logger.debug(
            "[%s] Source %d raw data: %s",
            dataclass_name,
            i,
            masked_raw,
        )

        source_entries.append(
            SourceEntry(
                index=i,
                file_path=str(src_path) if (src_path := source_item.file_path_for_errors()) is not None else None,
                loader_type=format_name,
                raw_data=raw,
            ),
        )

        source_ctxs.append(SourceContext(error_ctx=error_ctx, file_content=file_content))
        last_source = source_item
        last_resolved = resolved

        if merge_meta.strategy == MergeStrategyEnum.FIRST_FOUND:
            break

    if last_source is None or last_resolved is None:
        if merge_meta.sources:
            msg = f"All {len(merge_meta.sources)} source(s) failed to load"
        else:
            msg = "load() requires at least one Source for merge"
        source_error = SourceLoadError(message=msg)
        raise DatureConfigError(dataclass_name, [source_error])

    return LoadedSources(
        raw_dicts=raw_dicts,
        source_ctxs=source_ctxs,
        source_entries=source_entries,
        last_source=last_source,
        last_resolved=last_resolved,
        skipped_fields=skipped_fields,
    )
