import logging
from dataclasses import dataclass
from pathlib import Path

from dature.config import config
from dature.errors.exceptions import DatureConfigError, SourceLoadError, SourceLocation
from dature.errors.formatter import handle_load_errors
from dature.errors.location import ErrorContext, read_file_content
from dature.field_path import FieldPath
from dature.load_report import SourceEntry
from dature.loading.context import apply_skip_invalid, build_error_ctx
from dature.loading.resolver import resolve_loader, resolve_loader_class
from dature.masking.masking import mask_json_value
from dature.metadata import LoadMetadata, MergeMetadata, TypeLoader
from dature.protocols import DataclassInstance, LoaderProtocol
from dature.skip_field_provider import FilterResult
from dature.types import FILE_LIKE_TYPES, ExpandEnvVarsMode, FileOrStream, JSONValue

logger = logging.getLogger("dature")


def resolve_loader_for_source(
    *,
    loaders: tuple[LoaderProtocol, ...] | None,
    index: int,
    source_meta: LoadMetadata,
    expand_env_vars: ExpandEnvVarsMode | None = None,
    type_loaders: "tuple[TypeLoader, ...]" = (),
) -> LoaderProtocol:
    if loaders is not None:
        return loaders[index]
    return resolve_loader(source_meta, expand_env_vars=expand_env_vars, type_loaders=type_loaders)


def should_skip_broken(source_meta: LoadMetadata, merge_meta: MergeMetadata) -> bool:
    if source_meta.skip_if_broken is not None:
        if source_meta.file_ is None:
            logger.warning(
                "skip_if_broken has no effect on environment variable sources — they cannot be broken",
            )
        return source_meta.skip_if_broken
    return merge_meta.skip_broken_sources


def resolve_expand_env_vars(source_meta: LoadMetadata, merge_meta: MergeMetadata) -> ExpandEnvVarsMode:
    if source_meta.expand_env_vars is not None:
        return source_meta.expand_env_vars
    return merge_meta.expand_env_vars


def resolve_skip_invalid(
    source_meta: LoadMetadata,
    merge_meta: MergeMetadata,
) -> bool | tuple[FieldPath, ...]:
    if source_meta.skip_if_invalid is not None:
        return source_meta.skip_if_invalid
    return merge_meta.skip_invalid_fields


def resolve_mask_secrets(source_meta: LoadMetadata, merge_meta: MergeMetadata) -> bool:
    if source_meta.mask_secrets is not None:
        return source_meta.mask_secrets
    if merge_meta.mask_secrets is not None:
        return merge_meta.mask_secrets
    return config.masking.mask_secrets


def resolve_secret_field_names(source_meta: LoadMetadata, merge_meta: MergeMetadata) -> tuple[str, ...]:
    source_names = source_meta.secret_field_names or ()
    merge_names = merge_meta.secret_field_names or ()
    return source_names + merge_names


def apply_merge_skip_invalid(
    *,
    raw: JSONValue,
    source_meta: LoadMetadata,
    merge_meta: MergeMetadata,
    loader_instance: LoaderProtocol,
    dataclass_: type[DataclassInstance],
    source_index: int,
) -> FilterResult:
    skip_value = resolve_skip_invalid(source_meta, merge_meta)
    if not skip_value:
        return FilterResult(cleaned_dict=raw, skipped_paths=[])

    return apply_skip_invalid(
        raw=raw,
        skip_if_invalid=skip_value,
        loader_instance=loader_instance,
        dataclass_=dataclass_,
        log_prefix=f"[{dataclass_.__name__}] Source {source_index}:",
    )


@dataclass(frozen=True, slots=True)
class SourceContext:
    error_ctx: ErrorContext
    file_content: str | None


@dataclass(frozen=True, slots=True)
class SkippedFieldSource:
    metadata: LoadMetadata
    error_ctx: ErrorContext
    file_content: str | None


@dataclass(frozen=True, slots=True)
class LoadedSources:
    raw_dicts: list[JSONValue]
    source_ctxs: list[SourceContext]
    source_entries: list[SourceEntry]
    last_loader: LoaderProtocol
    skipped_fields: dict[str, list[SkippedFieldSource]]


def load_sources(  # noqa: C901, PLR0912, PLR0913, PLR0915
    *,
    merge_meta: MergeMetadata,
    dataclass_name: str,
    dataclass_: type[DataclassInstance],
    loaders: tuple[LoaderProtocol, ...] | None = None,
    secret_paths: frozenset[str] = frozenset(),
    mask_secrets: bool = False,
    type_loaders: "tuple[TypeLoader, ...]" = (),
) -> LoadedSources:
    raw_dicts: list[JSONValue] = []
    source_ctxs: list[SourceContext] = []
    source_entries: list[SourceEntry] = []
    last_loader: LoaderProtocol | None = None
    skipped_fields: dict[str, list[SkippedFieldSource]] = {}

    for i, source_meta in enumerate(merge_meta.sources):
        resolved_expand = resolve_expand_env_vars(source_meta, merge_meta)
        source_type_loaders = (source_meta.type_loaders or ()) + type_loaders
        loader_instance = resolve_loader_for_source(
            loaders=loaders,
            index=i,
            source_meta=source_meta,
            expand_env_vars=resolved_expand,
            type_loaders=source_type_loaders,
        )
        file_or_path: FileOrStream
        if isinstance(source_meta.file_, FILE_LIKE_TYPES):
            file_or_path = source_meta.file_
        elif source_meta.file_ is not None:
            file_or_path = Path(source_meta.file_)
        else:
            file_or_path = Path()
        error_ctx = build_error_ctx(source_meta, dataclass_name, secret_paths=secret_paths, mask_secrets=mask_secrets)

        def _load_raw(
            li: LoaderProtocol = loader_instance,
            fp: FileOrStream = file_or_path,
        ) -> JSONValue:
            return li.load_raw(fp)

        try:
            raw = handle_load_errors(
                func=_load_raw,
                ctx=error_ctx,
            )
        except (DatureConfigError, FileNotFoundError):
            if not should_skip_broken(source_meta, merge_meta):
                raise
            logger.warning(
                "[%s] Source %d skipped (broken): file=%s",
                dataclass_name,
                i,
                source_meta.file_
                if isinstance(source_meta.file_, (str, Path))
                else ("<stream>" if source_meta.file_ is not None else "<env>"),
            )
            continue
        except Exception as exc:
            if not should_skip_broken(source_meta, merge_meta):
                loader_class = resolve_loader_class(source_meta.loader, source_meta.file_)
                location = SourceLocation(
                    source_type=loader_class.display_name,
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
                source_meta.file_
                if isinstance(source_meta.file_, (str, Path))
                else ("<stream>" if source_meta.file_ is not None else "<env>"),
            )
            continue

        file_content = read_file_content(error_ctx.file_path)

        filter_result = apply_merge_skip_invalid(
            raw=raw,
            source_meta=source_meta,
            merge_meta=merge_meta,
            loader_instance=loader_instance,
            dataclass_=dataclass_,
            source_index=i,
        )

        for path in filter_result.skipped_paths:
            skipped_fields.setdefault(path, []).append(
                SkippedFieldSource(metadata=source_meta, error_ctx=error_ctx, file_content=file_content),
            )

        raw = filter_result.cleaned_dict
        raw_dicts.append(raw)

        loader_class = resolve_loader_class(source_meta.loader, source_meta.file_)
        display_name = loader_class.display_name

        logger.debug(
            "[%s] Source %d loaded: loader=%s, file=%s, keys=%s",
            dataclass_name,
            i,
            display_name,
            source_meta.file_
            if isinstance(source_meta.file_, (str, Path))
            else ("<stream>" if source_meta.file_ is not None else "<env>"),
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
                file_path=str(source_meta.file_) if isinstance(source_meta.file_, (str, Path)) else None,
                loader_type=display_name,
                raw_data=raw,
            ),
        )

        source_ctxs.append(SourceContext(error_ctx=error_ctx, file_content=file_content))
        last_loader = loader_instance

    if last_loader is None:
        if merge_meta.sources:
            msg = f"All {len(merge_meta.sources)} source(s) failed to load"
        else:
            msg = "MergeMetadata.sources must not be empty"
        source_error = SourceLoadError(message=msg)
        raise DatureConfigError(dataclass_name, [source_error])

    return LoadedSources(
        raw_dicts=raw_dicts,
        source_ctxs=source_ctxs,
        source_entries=source_entries,
        last_loader=last_loader,
        skipped_fields=skipped_fields,
    )
