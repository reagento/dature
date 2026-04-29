from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from dature.errors.exceptions import CaretSpan, LineRange, SourceLocation
from dature.masking.masking import mask_env_line
from dature.path_finders.base import PathFinder
from dature.types import JSONValue, NestedConflict, NestedConflicts

if TYPE_CHECKING:
    from dature.sources.base import Source


@dataclass(frozen=True)
class ErrorContext:
    dataclass_name: str
    source: "Source"
    secret_paths: frozenset[str] = frozenset()
    mask_secrets: bool = False
    nested_conflicts: NestedConflicts | None = None


def read_file_content(file_path: Path | None) -> str | None:
    if file_path is None:
        return None

    with suppress(OSError):
        return file_path.read_text()

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
    file_content: str,
    line_range: LineRange,
    secret_paths: frozenset[str],
    prefix: str | None,
    path_finder_class: type[PathFinder],
) -> bool:
    finder = path_finder_class(file_content)
    for secret_path in secret_paths:
        search_path = _build_search_path(secret_path.split("."), prefix)
        secret_range = finder.find_line_range(search_path)
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
    for location in locations:
        should_mask = is_secret
        if (
            not should_mask
            and ctx.secret_paths
            and location.line_range is not None
            and ctx.source.path_finder_class is not None
            and file_content is not None
        ):
            should_mask = _secret_overlaps_lines(
                file_content=file_content,
                line_range=location.line_range,
                secret_paths=ctx.secret_paths,
                prefix=ctx.source.prefix,
                path_finder_class=ctx.source.path_finder_class,
            )
        if should_mask and (location.line_content is not None or location.env_var_value is not None):
            masked_lines = (
                [mask_env_line(line) for line in location.line_content] if location.line_content is not None else None
            )
            masked_carets: list[CaretSpan] | None = None
            if masked_lines is not None:
                masked_carets = ctx.source._compute_line_carets(  # noqa: SLF001
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
) -> list[SourceLocation]:
    is_secret = ".".join(field_path) in ctx.secret_paths
    conflict = _resolve_conflict(field_path, ctx)

    locations = ctx.source.resolve_location(
        field_path=field_path,
        file_content=file_content,
        nested_conflict=conflict,
        input_value=input_value,
    )

    return _apply_masking(
        locations,
        ctx,
        file_content,
        is_secret=is_secret,
        field_path=field_path,
        input_value=input_value,
    )
