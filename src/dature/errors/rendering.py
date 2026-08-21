"""Error display rendering helpers: field-path/location text and exception stringification."""

import traceback

from dature.config import ErrorDisplayConfig
from dature.errors.loc_types import CaretSpan, SourceLocation

_ELLIPSIS_LEN = len("...")


def format_path(field_path: list[str]) -> str:
    return ".".join(field_path) or "<root>"


def _truncate_line(line: str, *, error_display: ErrorDisplayConfig) -> str:
    max_length = error_display.max_line_length
    if len(line) <= max_length:
        return line
    if max_length <= _ELLIPSIS_LEN:  # no room for the "..." marker
        return line[:max_length]
    return line[: max_length - _ELLIPSIS_LEN] + "..."


def _format_caret(caret: CaretSpan, *, error_display: ErrorDisplayConfig) -> str | None:
    if caret.length <= 0:
        return None
    max_visible = max(error_display.max_line_length - _ELLIPSIS_LEN, 0)
    if caret.start >= max_visible:
        return None
    return f"   │   {' ' * caret.start}{'^' * min(caret.length, max_visible - caret.start)}"


def _format_fileline(loc: SourceLocation, *, connector: str, suffix: str) -> str:
    line = f"   {connector} {loc.location_label} '{loc.file_path}'"
    if loc.line_range is not None:
        line += f", {loc.line_range!r}"
    return line + suffix


def _format_content_with_carets(
    content: list[str],
    carets: list[CaretSpan] | None,
    *,
    error_display: ErrorDisplayConfig,
) -> list[str]:
    max_visible = error_display.max_visible_lines
    truncated = len(content) > max_visible
    visible_count = max_visible - 1 if truncated else len(content)

    lines: list[str] = []
    for i in range(visible_count):
        lines.append(f"   ├── {_truncate_line(content[i], error_display=error_display)}")
        if (
            carets is not None
            and i < len(carets)
            and (rendered := _format_caret(carets[i], error_display=error_display)) is not None
        ):
            lines.append(rendered)
    if truncated:
        lines.append("   ├── ...")
    return lines


def format_location(
    loc: SourceLocation,
    *,
    error_display: ErrorDisplayConfig,
    last: bool = True,
) -> list[str]:
    connector = "└──" if last else "├──"
    suffix = f" ({loc.annotation})" if loc.annotation is not None else ""

    lines: list[str] = []
    if loc.line_content is not None:
        lines.extend(_format_content_with_carets(loc.line_content, loc.line_carets, error_display=error_display))

    if loc.env_var_name is not None and loc.file_path is None:
        lines.append(f"   {connector} {loc.location_label} '{loc.env_var_name}'" + suffix)
        return lines

    if loc.file_path:
        lines.append(_format_fileline(loc, connector=connector, suffix=suffix))
    return lines


def format_dature_error(exc: BaseException) -> str:
    """Render a DatureError / DatureConfigError (ExceptionGroup) as plain text."""
    if isinstance(exc, BaseExceptionGroup):
        return "".join(traceback.format_exception(type(exc), exc, None))
    return str(exc)
