from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from dature.errors.exceptions import LineRange, SourceLocation
from dature.masking.masking import mask_env_line
from dature.path_finders.base import PathFinder


@dataclass(frozen=True)
class ErrorContext:
    dataclass_name: str
    loader_type: str
    file_path: Path | None
    prefix: str | None
    split_symbols: str
    path_finder_class: type[PathFinder] | None
    secret_paths: frozenset[str] = frozenset()
    mask_secrets: bool = False


def read_file_content(file_path: Path | None) -> str | None:
    if file_path is None:
        return None

    with suppress(OSError):
        return file_path.read_text()

    return None


def _build_env_var_name(
    field_path: list[str],
    prefix: str | None,
    split_symbols: str,
) -> str:
    var_name = split_symbols.join(part.upper() for part in field_path)
    if prefix is not None:
        return prefix + var_name
    return var_name


def _build_search_path(field_path: list[str], prefix: str | None) -> list[str]:
    if not prefix:
        return field_path
    prefix_parts = prefix.split(".")
    return prefix_parts + field_path


def _find_env_line(content: str, var_name: str) -> SourceLocation:
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key == var_name:
            return SourceLocation(
                source_type="envfile",
                file_path=None,
                line_range=LineRange(start=i, end=i),
                line_content=[stripped],
                env_var_name=var_name,
            )
    return SourceLocation(
        source_type="envfile",
        file_path=None,
        line_range=None,
        line_content=None,
        env_var_name=var_name,
    )


def _empty_file_location(loader_type: str, file_path: Path | None) -> SourceLocation:
    return SourceLocation(
        source_type=loader_type,
        file_path=file_path,
        line_range=None,
        line_content=None,
        env_var_name=None,
    )


def _strip_common_indent(raw_lines: list[str]) -> list[str]:
    indents = [len(line) - len(line.lstrip()) for line in raw_lines if line.strip()]
    if not indents:
        return raw_lines
    min_indent = min(indents)
    return [line[min_indent:] for line in raw_lines]


def _resolve_file_location(
    field_path: list[str],
    loader_type: str,
    file_path: Path | None,
    file_content: str | None,
    prefix: str | None,
    path_finder_class: type[PathFinder] | None,
) -> SourceLocation:
    if file_content is None or not field_path:
        return _empty_file_location(loader_type, file_path)

    if path_finder_class is None:
        return _empty_file_location(loader_type, file_path)

    search_path = _build_search_path(field_path, prefix)
    finder = path_finder_class(file_content)
    line_range = finder.find_line_range(search_path)
    if line_range is None:
        return _empty_file_location(loader_type, file_path)

    lines = file_content.splitlines()
    content_lines: list[str] | None = None
    if 0 < line_range.start <= len(lines):
        end = min(line_range.end, len(lines))
        raw = lines[line_range.start - 1 : end]
        content_lines = _strip_common_indent(raw)

    return SourceLocation(
        source_type=loader_type,
        file_path=file_path,
        line_range=line_range,
        line_content=content_lines,
        env_var_name=None,
    )


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


def resolve_source_location(
    field_path: list[str],
    ctx: ErrorContext,
    file_content: str | None,
) -> SourceLocation:
    is_secret = ".".join(field_path) in ctx.secret_paths

    if ctx.loader_type == "env":
        env_var_name = _build_env_var_name(field_path, ctx.prefix, ctx.split_symbols)
        return SourceLocation(
            source_type="env",
            file_path=None,
            line_range=None,
            line_content=None,
            env_var_name=env_var_name,
        )

    if ctx.loader_type == "envfile":
        env_var_name = _build_env_var_name(field_path, ctx.prefix, ctx.split_symbols)
        if file_content is not None:
            location = _find_env_line(file_content, env_var_name)
            line_content = location.line_content
            if is_secret and line_content is not None:
                line_content = [mask_env_line(line) for line in line_content]
            return SourceLocation(
                source_type="envfile",
                file_path=ctx.file_path,
                line_range=location.line_range,
                line_content=line_content,
                env_var_name=env_var_name,
            )
        return SourceLocation(
            source_type="envfile",
            file_path=ctx.file_path,
            line_range=None,
            line_content=None,
            env_var_name=env_var_name,
        )

    if ctx.loader_type == "docker_secrets":
        secret_name = ctx.split_symbols.join(field_path)
        if ctx.prefix is not None:
            secret_name = ctx.prefix + secret_name
        secret_file = ctx.file_path / secret_name if ctx.file_path is not None else None
        return SourceLocation(
            source_type="docker_secrets",
            file_path=secret_file,
            line_range=None,
            line_content=None,
            env_var_name=None,
        )

    location = _resolve_file_location(
        field_path=field_path,
        loader_type=ctx.loader_type,
        file_path=ctx.file_path,
        file_content=file_content,
        prefix=ctx.prefix,
        path_finder_class=ctx.path_finder_class,
    )
    should_mask = is_secret
    if (
        not should_mask
        and ctx.secret_paths
        and location.line_range is not None
        and ctx.path_finder_class is not None
        and file_content is not None
    ):
        should_mask = _secret_overlaps_lines(
            file_content=file_content,
            line_range=location.line_range,
            secret_paths=ctx.secret_paths,
            prefix=ctx.prefix,
            path_finder_class=ctx.path_finder_class,
        )
    if should_mask and location.line_content is not None:
        masked_lines = [mask_env_line(line) for line in location.line_content]
        return SourceLocation(
            source_type=location.source_type,
            file_path=location.file_path,
            line_range=location.line_range,
            line_content=masked_lines,
            env_var_name=location.env_var_name,
        )
    return location
