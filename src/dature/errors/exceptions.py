from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from dature.config import config


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
    display_label: str
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


def _format_content_lines(content: list[str]) -> list[str]:
    max_visible = config.error_display.max_visible_lines
    if len(content) > max_visible:
        visible = content[: max_visible - 1]
        lines = [f"       {_truncate_line(line)}" for line in visible]
        lines.append("       ...")
        return lines

    return [f"       {_truncate_line(line)}" for line in content]


def _format_location(loc: SourceLocation, *, connector: str = "└──") -> list[str]:
    lines: list[str] = []
    suffix = f" ({loc.annotation})" if loc.annotation is not None else ""

    if loc.env_var_name is not None and loc.file_path is None:
        main = f"   {connector} {loc.display_label} '{loc.env_var_name}'"
        if loc.env_var_value is not None:
            main += f" = '{loc.env_var_value}'"
        lines.append(main + suffix)
    elif loc.file_path is not None:
        main = f"   {connector} {loc.display_label} '{loc.file_path}'"
        if loc.line_range is not None:
            main += f", {loc.line_range!r}"
        lines.append(main + suffix)
        if loc.line_content is not None:
            lines.extend(_format_content_lines(loc.line_content))

    return lines


class DatureError(Exception):
    """Базовая ошибка dature."""


class FieldLoadError(DatureError):
    def __init__(
        self,
        *,
        field_path: list[str],
        message: str,
        input_value: str | float | bool | None = None,
        locations: list[SourceLocation] | None = None,
    ) -> None:
        self.field_path = field_path
        self.message = message
        self.input_value = input_value
        self.locations = locations or []
        super().__init__(self._format())

    def _format(self) -> str:
        path_str = ".".join(self.field_path)
        if not path_str:
            path_str = "<root>"
        lines = [f"  [{path_str}]  {self.message}"]
        for i, loc in enumerate(self.locations):
            connector = "└──" if i == len(self.locations) - 1 else "├──"
            lines.extend(_format_location(loc, connector=connector))
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
        path_str = ".".join(self.field_path)
        if not path_str:
            path_str = "<root>"
        lines = [f"  [{path_str}]  {self.message}"]
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
            if err.field_path:
                path_str = ".".join(err.field_path)
            else:
                path_str = "<root>"
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
        lines: list[str] = []
        lines.append(f"{self.dataclass_name} merge conflicts ({len(self.exceptions)})")
        lines.append("")

        for exc in self.exceptions:
            if isinstance(exc, MergeConflictFieldError):
                path_str = ".".join(exc.field_path)
                if not path_str:
                    path_str = "<root>"
                lines.append(f"  [{path_str}]  {exc.message}")
                for loc in exc.locations:
                    lines.extend(_format_location(loc))
                lines.append("")
            else:
                lines.append(f"  {exc}")
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
        lines: list[str] = []
        lines.append(f"{self.dataclass_name} field group errors ({len(self.exceptions)})")
        lines.append("")

        for exc in self.exceptions:
            if isinstance(exc, FieldGroupViolationError):
                group_str = ", ".join(exc.group_fields)
                changed_pairs = zip(exc.changed_fields, exc.changed_sources, strict=True)
                changed_parts = [f"{field} (from source {src})" for field, src in changed_pairs]
                unchanged_pairs = zip(exc.unchanged_fields, exc.unchanged_sources, strict=True)
                unchanged_parts = [f"{field} (from source {src})" for field, src in unchanged_pairs]
                lines.append(
                    f"  Field group ({group_str}) partially overridden in source {exc.source_index}",
                )
                lines.append(f"    changed:   {', '.join(changed_parts)}")
                lines.append(f"    unchanged: {', '.join(unchanged_parts)}")
                lines.append("")
            else:
                lines.append(f"  {exc}")
                lines.append("")

        return "\n".join(lines)
