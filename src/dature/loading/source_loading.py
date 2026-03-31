import logging
from dataclasses import dataclass
from pathlib import Path

from dature.config import config
from dature.errors import DatureConfigError, SourceLoadError, SourceLocation
from dature.errors.formatter import handle_load_errors
from dature.errors.location import ErrorContext, read_filecontent
from dature.field_path import FieldPath
from dature.load_report import SourceEntry
from dature.loading.context import apply_skip_invalid, build_error_ctx
from dature.loading.resolver import resolve_loader, resolve_loader_class
from dature.masking.masking import mask_json_value
from dature.merging.strategy import MergeStrategyEnum
from dature.metadata import Source, _MergeConfig
from dature.protocols import DataclassInstance, LoaderProtocol
from dature.skip_field_provider import FilterResult
from dature.types import FILE_LIKE_TYPES, ExpandEnvVarsMode, FileOrStream, JSONValue, LoadRawResult, TypeLoaderMap

logger = logging.getLogger("dature")


def resolve_loader_for_source(
    *,
    loaders: tuple[LoaderProtocol, ...] | None,
    index: int,
    source_meta: Source,
    expand_env_vars: ExpandEnvVarsMode | None = None,
    type_loaders: TypeLoaderMap | None = None,
) -> LoaderProtocol:
    if loaders is not None:
        return loaders[index]
    return resolve_loader(source_meta, expand_env_vars=expand_env_vars, type_loaders=type_loaders)


def should_skip_broken(source_meta: Source, merge_meta: _MergeConfig) -> bool:
    if source_meta.skip_if_broken is not None:
        if source_meta.file is None:
            logger.warning(
                "skip_if_broken has no effect on environment variable sources — they cannot be broken",
            )
        return source_meta.skip_if_broken
    return merge_meta.skip_broken_sources


def resolve_expand_env_vars(source_meta: Source, merge_meta: _MergeConfig) -> ExpandEnvVarsMode:
    if source_meta.expand_env_vars is not None:
        return source_meta.expand_env_vars
    return merge_meta.expand_env_vars


def resolve_skip_invalid(
    source_meta: Source,
    merge_meta: _MergeConfig,
) -> bool | tuple[FieldPath, ...]:
    if source_meta.skip_if_invalid is not None:
        return source_meta.skip_if_invalid
    return merge_meta.skip_invalid_fields


def resolve_mask_secrets(source_meta: Source, merge_meta: _MergeConfig) -> bool:
    if source_meta.mask_secrets is not None:
        return source_meta.mask_secrets
    if merge_meta.mask_secrets is not None:
        return merge_meta.mask_secrets
    return config.masking.mask_secrets


def resolve_secret_field_names(source_meta: Source, merge_meta: _MergeConfig) -> tuple[str, ...]:
    source_names = source_meta.secret_field_names or ()
    merge_names = merge_meta.secret_field_names or ()
    return source_names + merge_names


def apply_merge_skip_invalid(
    *,
    raw: JSONValue,
    source_meta: Source,
    merge_meta: _MergeConfig,
    loader_instance: LoaderProtocol,
    schema: type[DataclassInstance],
    source_index: int,
) -> FilterResult:
    skip_value = resolve_skip_invalid(source_meta, merge_meta)
    if not skip_value:
        return FilterResult(cleaned_dict=raw, skipped_paths=[])

    return apply_skip_invalid(
        raw=raw,
        skip_if_invalid=skip_value,
        loader_instance=loader_instance,
        schema=schema,
        log_prefix=f"[{schema.__name__}] Source {source_index}:",
    )


@dataclass(frozen=True, slots=True)
class SourceContext:
    error_ctx: ErrorContext
    filecontent: str | None


@dataclass(frozen=True, slots=True)
class SkippedFieldSource:
    metadata: Source
    error_ctx: ErrorContext
    filecontent: str | None


@dataclass(frozen=True, slots=True)
class LoadedSources:
    raw_dicts: list[JSONValue]
    source_ctxs: list[SourceContext]
    source_entries: list[SourceEntry]
    last_loader: LoaderProtocol
    skipped_fields: dict[str, list[SkippedFieldSource]]


def load_sources(  # noqa: C901, PLR0912, PLR0913, PLR0915
    *,
    merge_meta: _MergeConfig,
    dataclass_name: str,
    schema: type[DataclassInstance],
    loaders: tuple[LoaderProtocol, ...] | None = None,
    secret_paths: frozenset[str] = frozenset(),
    mask_secrets: bool = False,
    type_loaders: TypeLoaderMap | None = None,
) -> LoadedSources:
    raw_dicts: list[JSONValue] = []
    source_ctxs: list[SourceContext] = []
    source_entries: list[SourceEntry] = []
    last_loader: LoaderProtocol | None = None
    skipped_fields: dict[str, list[SkippedFieldSource]] = {}

    for i, source_meta in enumerate(merge_meta.sources):
        resolved_expand = resolve_expand_env_vars(source_meta, merge_meta)
        source_type_loaders = {**(type_loaders or {}), **(source_meta.type_loaders or {})}
        loader_instance = resolve_loader_for_source(
            loaders=loaders,
            index=i,
            source_meta=source_meta,
            expand_env_vars=resolved_expand,
            type_loaders=source_type_loaders,
        )
        fileor_path: FileOrStream
        if isinstance(source_meta.file, FILE_LIKE_TYPES):
            fileor_path = source_meta.file
        elif source_meta.file is not None:
            fileor_path = Path(source_meta.file)
        else:
            fileor_path = Path()
        error_ctx = build_error_ctx(source_meta, dataclass_name, secret_paths=secret_paths, mask_secrets=mask_secrets)

        def _load_raw(
            li: LoaderProtocol = loader_instance,
            fp: FileOrStream = fileor_path,
        ) -> LoadRawResult:
            return li.load_raw(fp)

        try:
            load_result = handle_load_errors(
                func=_load_raw,
                ctx=error_ctx,
            )
        except (DatureConfigError, FileNotFoundError):
            if merge_meta.strategy != MergeStrategyEnum.FIRST_FOUND and not should_skip_broken(source_meta, merge_meta):
                raise
            logger.warning(
                "[%s] Source %d skipped (broken): file=%s",
                dataclass_name,
                i,
                source_meta.file
                if isinstance(source_meta.file, (str, Path))
                else ("<stream>" if source_meta.file is not None else "<env>"),
            )
            continue
        except Exception as exc:
            if merge_meta.strategy != MergeStrategyEnum.FIRST_FOUND and not should_skip_broken(source_meta, merge_meta):
                loader_class = resolve_loader_class(source_meta.loader, source_meta.file)
                location = SourceLocation(
                    display_label=loader_class.display_label,
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
                source_meta.file
                if isinstance(source_meta.file, (str, Path))
                else ("<stream>" if source_meta.file is not None else "<env>"),
            )
            continue

        raw = load_result.data
        if load_result.nested_conflicts:
            error_ctx = build_error_ctx(
                source_meta,
                dataclass_name,
                secret_paths=secret_paths,
                mask_secrets=mask_secrets,
                nested_conflicts=load_result.nested_conflicts,
            )

        filecontent = read_filecontent(error_ctx.file_path)

        filter_result = apply_merge_skip_invalid(
            raw=raw,
            source_meta=source_meta,
            merge_meta=merge_meta,
            loader_instance=loader_instance,
            schema=schema,
            source_index=i,
        )

        for path in filter_result.skipped_paths:
            skipped_fields.setdefault(path, []).append(
                SkippedFieldSource(metadata=source_meta, error_ctx=error_ctx, filecontent=filecontent),
            )

        raw = filter_result.cleaned_dict
        raw_dicts.append(raw)

        loader_class = resolve_loader_class(source_meta.loader, source_meta.file)
        display_name = loader_class.display_name

        logger.debug(
            "[%s] Source %d loaded: loader=%s, file=%s, keys=%s",
            dataclass_name,
            i,
            display_name,
            source_meta.file
            if isinstance(source_meta.file, (str, Path))
            else ("<stream>" if source_meta.file is not None else "<env>"),
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
                file_path=str(source_meta.file) if isinstance(source_meta.file, (str, Path)) else None,
                loader_type=display_name,
                raw_data=raw,
            ),
        )

        source_ctxs.append(SourceContext(error_ctx=error_ctx, filecontent=filecontent))
        last_loader = loader_instance

        if merge_meta.strategy == MergeStrategyEnum.FIRST_FOUND:
            break

    if last_loader is None:
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
        last_loader=last_loader,
        skipped_fields=skipped_fields,
    )
