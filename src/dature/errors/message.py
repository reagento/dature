"""Error message formatting helpers."""

from typing import TYPE_CHECKING

from dature.config import config

if TYPE_CHECKING:
    from dature.errors.exceptions import CaretSpan, SourceLocation


def format_path(field_path: list[str]) -> str:
    return ".".join(field_path) or "<root>"


def _truncate_line(line: str) -> str:
    max_length = config.error_display.max_line_length
    if len(line) > max_length:
        return line[: max_length - 3] + "..."
    return line


def _format_caret(caret: "CaretSpan") -> str | None:
    if caret.length <= 0:
        return None
    max_visible = config.error_display.max_line_length - 3
    if caret.start >= max_visible:
        return None
    return f"   │   {' ' * caret.start}{'^' * min(caret.length, max_visible - caret.start)}"


def _format_fileline(loc: "SourceLocation", *, connector: str, suffix: str) -> str:
    line = f"   {connector} {loc.location_label} '{loc.file_path}'"
    if loc.line_range is not None:
        line += f", {loc.line_range!r}"
    return line + suffix


def _format_content_with_carets(
    content: list[str],
    carets: "list[CaretSpan] | None",
) -> list[str]:
    max_visible = config.error_display.max_visible_lines
    truncated = len(content) > max_visible
    visible_count = max_visible - 1 if truncated else len(content)

    lines: list[str] = []
    for i in range(visible_count):
        lines.append(f"   ├── {_truncate_line(content[i])}")
        if carets is not None and i < len(carets) and (rendered := _format_caret(carets[i])) is not None:
            lines.append(rendered)
    if truncated:
        lines.append("   ├── ...")
    return lines


def format_location(
    loc: "SourceLocation",
    *,
    last: bool = True,
) -> list[str]:
    connector = "└──" if last else "├──"
    suffix = f" ({loc.annotation})" if loc.annotation is not None else ""

    lines: list[str] = []
    if loc.line_content is not None:
        lines.extend(_format_content_with_carets(loc.line_content, loc.line_carets))

    if loc.env_var_name is not None and loc.file_path is None:
        lines.append(f"   {connector} {loc.location_label} '{loc.env_var_name}'" + suffix)
        return lines

    if loc.file_path is None:
        return []

    lines.append(_format_fileline(loc, connector=connector, suffix=suffix))
    return lines
