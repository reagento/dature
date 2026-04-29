import logging
from dataclasses import dataclass

from dature.config import config
from dature.errors.location import ErrorContext
from dature.field_path import FieldPath
from dature.loading.context import apply_skip_invalid
from dature.loading.merge_config import MergeConfig
from dature.protocols import DataclassInstance
from dature.skip_field_provider import FilterResult
from dature.sources.base import Source
from dature.types import (
    JSONValue,
    TypeLoaderMap,
)

logger = logging.getLogger("dature")


def resolve_type_loaders(
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
    if source.skip_field_if_invalid is not None:
        return source.skip_field_if_invalid
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
        skip_field_if_invalid=skip_value,
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
