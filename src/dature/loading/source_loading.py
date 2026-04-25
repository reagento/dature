import copy
import dataclasses
import logging
from dataclasses import dataclass

from dature.config import config
from dature.errors import DatureConfigError, SourceLoadError, SourceLocation
from dature.errors.formatter import handle_load_errors
from dature.errors.location import ErrorContext, read_file_content
from dature.field_path import FieldPath
from dature.load_report import SourceEntry
from dature.loading.context import apply_skip_invalid, build_error_ctx
from dature.loading.merge_config import MergeConfig, SourceParams
from dature.masking.masking import mask_json_value
from dature.merging.strategy import MergeStrategyEnum
from dature.protocols import DataclassInstance
from dature.skip_field_provider import FilterResult
from dature.sources.base import Source
from dature.types import (
    JSONValue,
    TypeLoaderMap,
)

logger = logging.getLogger("dature")


def _apply_source_init_params(source: Source, params: SourceParams) -> Source:
    """Inject load-level params into source fields (source > load > config).

    Iterates SourceParams fields by name and matches them against the source's
    dataclass fields. For each matching field currently None: applies
    load-level value, or falls back to config.loading.<same_name> if available.
    """
    source_field_names = {f.name for f in dataclasses.fields(source) if f.init}
    overrides: dict[str, object] = {}

    for f in dataclasses.fields(params):
        name = f.name
        if name not in source_field_names:
            continue
        if getattr(source, name, None) is not None:
            continue  # source-level takes priority
        load_val = getattr(params, name)
        config_val = getattr(config.loading, name, None)
        effective = load_val if load_val is not None else config_val
        if effective is not None:
            overrides[name] = effective

    if not overrides:
        return source

    new_source = copy.copy(source)
    vars(new_source).update(overrides)
    return new_source


def _resolve_type_loaders(
    source: Source,
    load_type_loaders: TypeLoaderMap | None,
) -> TypeLoaderMap | None:
    merged = {**config.type_loaders, **(load_type_loaders or {}), **(source.type_loaders or {})}
    return merged or None


def should_skip_broken(source: Source, merge_meta: MergeConfig) -> bool:
    if source.skip_if_broken is not None:
        if source.file_display() is None:
            logger.warning(
                "skip_if_broken has no effect on non-file sources — they cannot be broken",
            )
        return source.skip_if_broken
    return merge_meta.skip_broken_sources


def resolve_skip_invalid(
    source: Source,
    merge_meta: MergeConfig,
) -> bool | tuple[FieldPath, ...]:
    if source.skip_if_invalid is not None:
        return source.skip_if_invalid
    return merge_meta.skip_invalid_fields


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
    last_type_loaders: TypeLoaderMap | None
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
    last_type_loaders: TypeLoaderMap | None = None
    skipped_fields: dict[str, list[SkippedFieldSource]] = {}

    for i, raw_source in enumerate(merge_meta.sources):
        source_item = _apply_source_init_params(raw_source, merge_meta.source_params)
        type_loaders = _resolve_type_loaders(source_item, merge_meta.type_loaders)
        error_ctx = build_error_ctx(source_item, dataclass_name, secret_paths=secret_paths, mask_secrets=mask_secrets)

        try:
            load_result = handle_load_errors(
                func=source_item.load_raw,
                ctx=error_ctx,
            )
        except (DatureConfigError, FileNotFoundError):
            if merge_meta.strategy != MergeStrategyEnum.FIRST_FOUND and not should_skip_broken(source_item, merge_meta):
                raise
            logger.warning(
                "[%s] Source %d skipped (broken): file=%s",
                dataclass_name,
                i,
                source_item.display_name(),
            )
            continue
        except Exception as exc:
            if merge_meta.strategy != MergeStrategyEnum.FIRST_FOUND and not should_skip_broken(source_item, merge_meta):
                location = SourceLocation(
                    location_label=source_item.location_label,
                    file_path=error_ctx.source.file_path_for_errors(),
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
                source_item.display_name(),
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

        file_content = read_file_content(error_ctx.source.file_path_for_errors())

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
            source_item.display_name(),
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
                file_path=str(src_path)
                if (src_path := source_item.file_path_for_errors()) is not None
                else source_item.display_name(),
                loader_type=format_name,
                raw_data=raw,
            ),
        )

        source_ctxs.append(SourceContext(error_ctx=error_ctx, file_content=file_content))
        last_source = source_item
        last_type_loaders = type_loaders

        if merge_meta.strategy == MergeStrategyEnum.FIRST_FOUND:
            break

    if last_source is None:
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
        last_type_loaders=last_type_loaders,
        skipped_fields=skipped_fields,
    )
