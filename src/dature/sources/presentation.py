"""Caret / line-range presentation helpers for error location rendering.

Free functions extracted from ``Source`` — they use no instance state.
Called internally by ``Source.resolve_location`` and ``FlatKeySource``
subclasses that build custom error locations.
"""

import json
from pathlib import Path

from dature.errors import CaretSpan, LineRange, SourceLocation
from dature.type_aliases import JSONValue, NestedConflict


def empty_location(location_label: str, file_path: Path | None) -> SourceLocation:
    return SourceLocation(
        location_label=location_label,
        file_path=file_path,
        line_range=None,
        line_content=None,
        env_var_name=None,
    )


def build_search_path(field_path: list[str], prefix: str | None) -> list[str]:
    if not prefix:
        return field_path
    prefix_parts = prefix.split(".")
    return prefix_parts + field_path


def find_parent_line_range(
    line_index: "dict[tuple[str, ...], LineRange]",
    search_path: list[str],
) -> "LineRange | None":
    path = search_path[:-1]
    while path:
        line_range = line_index.get(tuple(path))
        if line_range is not None:
            return line_range
        path = path[:-1]
    return None


def strip_common_indent(raw_lines: list[str]) -> list[str]:
    indents = [len(line) - len(line.lstrip()) for line in raw_lines if line.strip()]
    if not indents:
        return raw_lines
    min_indent = min(indents)
    return [line[min_indent:] for line in raw_lines]


def build_value_candidates(input_value: JSONValue) -> list[str]:
    if isinstance(input_value, (list, dict)):
        return [json.dumps(input_value, ensure_ascii=False)]
    if isinstance(input_value, str) and input_value == "":
        return ['""', "''"]
    text = str(input_value)
    lower = text.lower()
    if lower == text:
        return [text]
    return [text, lower]


def find_value_in_line(
    line: str,
    *,
    input_value: JSONValue,
    field_key: str | None = None,
    search_from: int = 0,
) -> "CaretSpan | None":
    candidates = build_value_candidates(input_value)
    if field_key is not None:
        for key_marker in (f'"{field_key}":', f"{field_key}:"):
            key_pos = line.find(key_marker)
            if key_pos != -1:
                after_key = key_pos + len(key_marker)
                for candidate in candidates:
                    pos = line.find(candidate, after_key)
                    if pos != -1:
                        return CaretSpan(start=pos, end=pos + len(candidate))
    for candidate in candidates:
        pos = line.rfind(candidate, search_from)
        if pos != -1:
            return CaretSpan(start=pos, end=pos + len(candidate))
    return None


def nonwhitespace_span(line: str) -> "CaretSpan":
    stripped = line.lstrip()
    if not stripped:
        return CaretSpan(start=0, end=0)
    pos = len(line) - len(stripped)
    return CaretSpan(start=pos, end=len(line))


def caret_for_key_line(line: str) -> "CaretSpan":
    sep_pos = max(line.rfind(":"), line.rfind("="))
    if sep_pos != -1:
        after = sep_pos + 1
        while after < len(line) and line[after] == " ":
            after += 1
        if after < len(line):
            return CaretSpan(start=after, end=len(line))
    return nonwhitespace_span(line)


def compute_line_carets(
    content_lines: list[str],
    *,
    input_value: JSONValue,
    field_key: str | None,
) -> "list[CaretSpan]":
    """Compute caret spans pointing at *input_value* within *content_lines*."""
    if len(content_lines) == 1:
        if input_value is None:
            return [caret_for_key_line(content_lines[0])]
        found = find_value_in_line(
            content_lines[0],
            input_value=input_value,
            field_key=field_key,
        )
        return [found if found is not None else CaretSpan(start=0, end=0)]
    if field_key is not None and input_value is not None:
        for index, content_line in enumerate(content_lines):
            found = find_value_in_line(content_line, input_value=input_value, field_key=field_key)
            if found is not None:
                return [found if i == index else CaretSpan(start=0, end=0) for i in range(len(content_lines))]
    return [caret_for_key_line(content_lines[0])] + [CaretSpan(start=0, end=0) for _ in content_lines[1:]]


def value_line_carets(
    value_lines: list[str],
    value_start: int,
    first_caret: "CaretSpan | None" = None,
) -> "list[CaretSpan]":
    """Build caret spans for a multi-line value starting at *value_start*."""
    effective_first = (
        first_caret if first_caret is not None else CaretSpan(start=value_start, end=value_start + len(value_lines[0]))
    )
    result = [effective_first]
    result.extend(CaretSpan(start=0, end=len(line)) for line in value_lines[1:])
    return result


def resolve_var_name(
    field_path: list[str],
    prefix: str | None,
    nested_sep: str,
    conflict: NestedConflict | None,
) -> str:
    """Build an env-var name from *field_path*, honouring *conflict* resolution."""

    def _build_name(parts: list[str]) -> str:
        var_name = nested_sep.join(part.upper() for part in parts)
        if prefix is not None:
            return prefix + var_name
        return var_name

    json_var = _build_name(field_path[:1])
    if conflict is not None and conflict.used_var == json_var:
        return json_var
    return _build_name(field_path)
