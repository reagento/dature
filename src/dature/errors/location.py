from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from dature.errors.exceptions import LineRange, SourceLocation
from dature.masking.masking import mask_env_line
from dature.types import NestedConflict, NestedConflicts

if TYPE_CHECKING:
    from dature.protocols import LoaderProtocol


@dataclass(frozen=True)
class ErrorContext:
    dataclass_name: str
    loader_class: "type[LoaderProtocol]"
    file_path: Path | None
    prefix: str | None
    split_symbols: str
    secret_paths: frozenset[str] = frozenset()
    mask_secrets: bool = False
    nested_conflicts: NestedConflicts | None = None


def read_filecontent(file_path: Path | None) -> str | None:
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
    filecontent: str,
    line_range: LineRange,
    secret_paths: frozenset[str],
    prefix: str | None,
    path_finder_class: type,
) -> bool:
    finder = path_finder_class(filecontent)
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
    filecontent: str | None,
    *,
    is_secret: bool,
) -> list[SourceLocation]:
    result: list[SourceLocation] = []
    for location in locations:
        should_mask = is_secret
        if (
            not should_mask
            and ctx.secret_paths
            and location.line_range is not None
            and ctx.loader_class.path_finder_class is not None
            and filecontent is not None
        ):
            should_mask = _secret_overlaps_lines(
                filecontent=filecontent,
                line_range=location.line_range,
                secret_paths=ctx.secret_paths,
                prefix=ctx.prefix,
                path_finder_class=ctx.loader_class.path_finder_class,
            )
        if should_mask and location.line_content is not None:
            masked_lines = [mask_env_line(line) for line in location.line_content]
            result.append(
                SourceLocation(
                    display_label=location.display_label,
                    file_path=location.file_path,
                    line_range=location.line_range,
                    line_content=masked_lines,
                    env_var_name=location.env_var_name,
                ),
            )
        else:
            result.append(location)
    return result


def resolve_source_location(
    field_path: list[str],
    ctx: ErrorContext,
    filecontent: str | None,
) -> list[SourceLocation]:
    is_secret = ".".join(field_path) in ctx.secret_paths
    conflict = _resolve_conflict(field_path, ctx)

    locations = ctx.loader_class.resolve_location(
        field_path,
        ctx.file_path,
        filecontent,
        ctx.prefix,
        ctx.split_symbols,
        conflict,
    )

    return _apply_masking(locations, ctx, filecontent, is_secret=is_secret)
