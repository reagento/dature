from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from dature.errors.loc_types import CaretSpan, LineRange, SourceLocation
from dature.masking.masking import mask_env_line
from dature.sources.protocol import FileSourceProtocol, SourceProtocol
from dature.type_aliases import JSONValue, NestedConflict, NestedConflicts


@dataclass(frozen=True)
class ErrorContext:
    dataclass_name: str
    source: SourceProtocol
    secret_paths: frozenset[str] = frozenset()
    mask_secrets: bool = False
    nested_conflicts: NestedConflicts | None = None


@dataclass(frozen=True, slots=True)
class SourceContext:
    error_ctx: ErrorContext
    file_content: str | None
    loaded_data: "JSONValue"


@dataclass(frozen=True, slots=True)
class SkippedFieldSource:
    source: SourceProtocol
    error_ctx: ErrorContext
    file_content: str | None
    loaded_data: "JSONValue"


def read_file_content(file_path: Path | None, encoding: str | None = None) -> str | None:
    if file_path is None:
        return None

    with suppress(OSError, UnicodeDecodeError):
        return file_path.read_text(encoding=encoding)

    return None


def _build_search_path(field_path: list[str], prefix: str | None) -> list[str]:
    if not prefix:
        return field_path
    prefix_parts = prefix.split(".")
    return prefix_parts + field_path


def _ranges_overlap(a: LineRange, b: LineRange) -> bool:
    return a.start <= b.end and b.start <= a.end


def _secret_overlaps_lines(
    *,
    line_index: dict[tuple[str, ...], LineRange],
    line_range: LineRange,
    secret_paths: frozenset[str],
    prefix: str | None,
) -> bool:
    for secret_path in secret_paths:
        search_path = _build_search_path(secret_path.split("."), prefix)
        secret_range = line_index.get(tuple(search_path))
        if secret_range is not None and _ranges_overlap(line_range, secret_range):
            return True
    return False


def _resolve_conflict(
    field_path: list[str],
    ctx: ErrorContext,
) -> NestedConflict | None:
    if ctx.nested_conflicts is None:
        return None
    field_key = field_path[0] if field_path else ""
    return ctx.nested_conflicts.get(field_key)


def _apply_masking(
    locations: list[SourceLocation],
    ctx: ErrorContext,
    file_content: str | None,
    *,
    is_secret: bool,
    field_path: list[str],
    input_value: JSONValue,
) -> list[SourceLocation]:
    result: list[SourceLocation] = []
    field_key = field_path[-1] if field_path else None
    line_index = (
        ctx.source.build_line_index(file_content)
        if ctx.secret_paths and file_content is not None and isinstance(ctx.source, FileSourceProtocol)
        else None
    )
    for location in locations:
        should_mask = is_secret
        if not should_mask and ctx.secret_paths and location.line_range is not None and line_index is not None:
            should_mask = _secret_overlaps_lines(
                line_index=line_index,
                line_range=location.line_range,
                secret_paths=ctx.secret_paths,
                prefix=ctx.source.prefix,
            )
        if should_mask and (location.line_content is not None or location.env_var_value is not None):
            masked_lines = (
                [mask_env_line(line) for line in location.line_content] if location.line_content is not None else None
            )
            masked_carets: list[CaretSpan] | None = None
            if masked_lines is not None:
                masked_carets = ctx.source.compute_line_carets(
                    masked_lines,
                    input_value=input_value,
                    field_key=field_key,
                )
            result.append(
                SourceLocation(
                    location_label=location.location_label,
                    file_path=location.file_path,
                    line_range=location.line_range,
                    line_content=masked_lines,
                    env_var_name=location.env_var_name,
                    line_carets=masked_carets,
                    # env_var_value intentionally omitted — drop it when masking
                ),
            )
        else:
            result.append(location)
    return result


def resolve_source_location(
    field_path: list[str],
    ctx: ErrorContext,
    file_content: str | None,
    *,
    input_value: JSONValue = None,
    loaded_data: "JSONValue | None" = None,
) -> list[SourceLocation]:
    is_secret = ".".join(field_path) in ctx.secret_paths
    conflict = _resolve_conflict(field_path, ctx)

    locations = ctx.source.resolve_location(
        field_path=field_path,
        nested_conflict=conflict,
        input_value=input_value,
        loaded_data=loaded_data,
    )

    return _apply_masking(
        locations,
        ctx,
        file_content,
        is_secret=is_secret,
        field_path=field_path,
        input_value=input_value,
    )
