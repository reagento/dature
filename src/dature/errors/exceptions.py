import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from dature.config import config
from dature.types import JSONValue


@dataclass(frozen=True, slots=True)
class LineRange:
    start: int
    end: int

    def __repr__(self) -> str:
        if self.start == self.end:
            return f"line {self.start}"
        return f"line {self.start}-{self.end}"


@dataclass(frozen=True, slots=True)
class SourceLocation:
    location_label: str
    file_path: Path | None
    line_range: LineRange | None
    line_content: list[str] | None
    env_var_name: str | None
    annotation: str | None = None
    env_var_value: str | None = None


def _truncate_line(line: str) -> str:
    max_length = config.error_display.max_line_length
    if len(line) > max_length:
        return line[: max_length - 3] + "..."
    return line


def _format_content_lines(content: list[str], *, prefix: str = "       ") -> list[str]:
    max_visible = config.error_display.max_visible_lines
    if len(content) > max_visible:
        visible = content[: max_visible - 1]
        lines = [f"{prefix}{_truncate_line(line)}" for line in visible]
        lines.append(f"{prefix}...")
        return lines

    return [f"{prefix}{_truncate_line(line)}" for line in content]


@dataclass(frozen=True, slots=True)
class _FoundValue:
    pos: int
    length: int


def _build_candidates(input_value: JSONValue) -> list[str]:
    if isinstance(input_value, (list, dict)):
        return [json.dumps(input_value, ensure_ascii=False)]

    if isinstance(input_value, str) and input_value == "":
        return ['""', "''"]

    text = str(input_value)
    lower = text.lower()
    if lower == text:
        return [text]
    return [text, lower]


def _find_value_position(line: str, *, input_value: JSONValue) -> _FoundValue | None:
    if input_value is None:
        return None
    for candidate in _build_candidates(input_value):
        pos = line.rfind(candidate)
        if pos != -1:
            return _FoundValue(pos=pos, length=len(candidate))
    return None


def _format_location(
    loc: SourceLocation,
    *,
    connector: str = "└──",
    input_value: JSONValue = None,
    is_last: bool = True,
) -> list[str]:
    suffix = f" ({loc.annotation})" if loc.annotation is not None else ""

    if loc.env_var_name is not None and loc.file_path is None:
        main = f"   {connector} {loc.location_label} '{loc.env_var_name}'"
        if loc.env_var_value is not None:
            main += f" = '{loc.env_var_value}'"
        return [main + suffix]

    if loc.file_path is None:
        return []

    if loc.line_content is not None and input_value is not None and len(loc.line_content) == 1:
        found = _find_value_position(loc.line_content[0], input_value=input_value)
        if found is not None:
            max_visible = config.error_display.max_line_length - 3
            if found.pos < max_visible:
                caret_len = min(found.length, max_visible - found.pos)
                return [
                    *_format_content_lines(loc.line_content, prefix="   ├── "),
                    f"   │   {' ' * found.pos}{'^' * caret_len}",
                    *_format_fileline(loc, connector="└──" if is_last else "├──", suffix=suffix),
                ]

    if loc.line_content is not None:
        return [
            *_format_content_lines(loc.line_content, prefix="   ├── "),
            *_format_fileline(loc, connector="└──" if is_last else "├──", suffix=suffix),
        ]

    return _format_fileline(loc, connector="└──" if is_last else "├──", suffix=suffix)


def _format_fileline(loc: SourceLocation, *, connector: str, suffix: str = "") -> list[str]:
    filemain = f"   {connector} {loc.location_label} '{loc.file_path}'"
    if loc.line_range is not None:
        filemain += f", {loc.line_range!r}"
    return [filemain + suffix]


def _format_path(field_path: list[str]) -> str:
    return ".".join(field_path) or "<root>"


class DatureError(Exception):
    """Base dature error."""


class FieldLoadError(DatureError):
    def __init__(
        self,
        *,
        field_path: list[str],
        message: str,
        input_value: JSONValue = None,
        locations: list[SourceLocation] | None = None,
    ) -> None:
        self.field_path = field_path
        self.message = message
        self.input_value = input_value
        self.locations = locations or []
        super().__init__(self._format())

    def _format(self) -> str:
        lines = [f"  [{_format_path(self.field_path)}]  {self.message}"]
        for i, loc in enumerate(self.locations):
            is_last = i == len(self.locations) - 1
            connector = "└──" if is_last else "├──"
            lines.extend(
                _format_location(
                    loc,
                    connector=connector,
                    input_value=self.input_value,
                    is_last=is_last,
                ),
            )
        return "\n".join(lines)


class MergeConflictFieldError(DatureError):
    def __init__(
        self,
        *,
        field_path: list[str],
        message: str,
        locations: list[SourceLocation],
    ) -> None:
        self.field_path = field_path
        self.message = message
        self.locations = locations
        super().__init__(self._format())

    def _format(self) -> str:
        lines = [f"  [{_format_path(self.field_path)}]  {self.message}"]
        for loc in self.locations:
            lines.extend(_format_location(loc))
        return "\n".join(lines)


class SourceLoadError(DatureError):
    def __init__(
        self,
        *,
        message: str,
        location: SourceLocation | None = None,
    ) -> None:
        self.message = message
        self.location = location
        super().__init__(message)


class MissingEnvVarError(DatureError):
    def __init__(
        self,
        *,
        var_name: str,
        position: int,
        source_text: str,
        field_path: list[str] | None = None,
        location: SourceLocation | None = None,
    ) -> None:
        self.var_name = var_name
        self.position = position
        self.source_text = source_text
        self.field_path = field_path or []
        self.location = location
        super().__init__(
            f"Environment variable '{var_name}' is not set (position {position} in '{source_text}')",
        )


class DatureConfigError(ExceptionGroup[DatureError]):
    dataclass_name: str

    def __new__(
        cls,
        dataclass_name: str,
        errors: Sequence[DatureError],
    ) -> Self:
        obj = super().__new__(
            cls,
            f"{dataclass_name} loading errors ({len(errors)})",
            errors,
        )
        obj.dataclass_name = dataclass_name
        return obj

    def __init__(
        self,
        dataclass_name: str,
        errors: Sequence[DatureError],
    ) -> None:
        pass

    def derive(self, excs: Sequence[DatureError], /) -> Self:  # type: ignore[override]
        return self.__class__(self.dataclass_name, list(excs))

    def __str__(self) -> str:
        return f"{self.dataclass_name} loading errors ({len(self.exceptions)})"


class EnvVarExpandError(DatureConfigError):
    def __new__(
        cls,
        errors: Sequence[MissingEnvVarError],
        *,
        dataclass_name: str = "",
    ) -> Self:
        obj = super().__new__(cls, dataclass_name, errors)
        obj.dataclass_name = dataclass_name
        return obj

    def __init__(
        self,
        errors: Sequence[MissingEnvVarError],
        *,
        dataclass_name: str = "",
    ) -> None:
        pass

    def derive(self, excs: Sequence[MissingEnvVarError], /) -> Self:  # type: ignore[override]
        return self.__class__(list(excs), dataclass_name=self.dataclass_name)

    def __str__(self) -> str:
        if self.dataclass_name:
            header = f"{self.dataclass_name} env expand errors ({len(self.exceptions)})"
        else:
            header = f"Missing environment variables ({len(self.exceptions)})"
        lines: list[str] = [header, ""]

        for err in self.exceptions:
            if not isinstance(err, MissingEnvVarError):
                continue
            path_str = _format_path(err.field_path)
            lines.append(f"  [{path_str}]  Missing environment variable '{err.var_name}'")
            if err.location is not None:
                lines.extend(_format_location(err.location))
            lines.append("")

        return "\n".join(lines)


class MergeConflictError(DatureConfigError):
    def __new__(
        cls,
        dataclass_name: str,
        errors: Sequence[MergeConflictFieldError],
    ) -> Self:
        return super().__new__(cls, dataclass_name, errors)

    def __str__(self) -> str:
        lines = [f"{self.dataclass_name} merge conflicts ({len(self.exceptions)})", ""]
        for exc in self.exceptions:
            lines.append(str(exc))
            lines.append("")
        return "\n".join(lines)


class FieldGroupViolationError(DatureError):
    def __init__(
        self,
        *,
        group_fields: tuple[str, ...],
        changed_fields: tuple[str, ...],
        unchanged_fields: tuple[str, ...],
        changed_sources: tuple[str, ...],
        unchanged_sources: tuple[str, ...],
        source_index: int,
    ) -> None:
        self.group_fields = group_fields
        self.changed_fields = changed_fields
        self.unchanged_fields = unchanged_fields
        self.changed_sources = changed_sources
        self.unchanged_sources = unchanged_sources
        self.source_index = source_index
        super().__init__(self._format())

    def _format(self) -> str:
        group_str = ", ".join(self.group_fields)
        changed_pairs = zip(self.changed_fields, self.changed_sources, strict=True)
        changed_parts = [f"{field} (from source {src})" for field, src in changed_pairs]
        unchanged_pairs = zip(self.unchanged_fields, self.unchanged_sources, strict=True)
        unchanged_parts = [f"{field} (from source {src})" for field, src in unchanged_pairs]
        lines = [
            f"  Field group ({group_str}) partially overridden in source {self.source_index}",
            f"    changed:   {', '.join(changed_parts)}",
            f"    unchanged: {', '.join(unchanged_parts)}",
        ]
        return "\n".join(lines)


class FieldGroupError(DatureConfigError):
    def __new__(
        cls,
        dataclass_name: str,
        errors: Sequence[FieldGroupViolationError],
    ) -> Self:
        return super().__new__(cls, dataclass_name, errors)

    def __str__(self) -> str:
        return f"{self.dataclass_name} field group errors ({len(self.exceptions)})"
