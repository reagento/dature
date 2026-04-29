from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from dature.errors.message import format_location, format_path
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
class CaretSpan:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class SourceLocation:
    location_label: str
    file_path: Path | None
    line_range: LineRange | None
    line_content: list[str] | None
    env_var_name: str | None
    annotation: str | None = None
    env_var_value: str | None = None
    line_carets: "list[CaretSpan] | None" = None


class DatureError(Exception):
    """Base dature error."""


class ValidatorTypeError(DatureError):
    """Raised at schema-build time when a V-predicate is incompatible with a field's type.

    Unlike FieldLoadError, this is not a data-validation failure — it signals that
    the schema itself is ill-formed (e.g., ``V.len()`` applied to an ``int`` field).
    It is raised before any configuration data is read.
    """

    def __init__(
        self,
        *,
        field_path: list[str],
        message: str,
    ) -> None:
        self.field_path = field_path
        self.message = message
        super().__init__(message)


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
        lines = [f"  [{format_path(self.field_path)}]  {self.message}"]
        last_idx = len(self.locations) - 1
        for i, loc in enumerate(self.locations):
            lines.extend(format_location(loc, last=i == last_idx))
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
        lines = [f"  [{format_path(self.field_path)}]  {self.message}"]
        for loc in self.locations:
            lines.extend(format_location(loc))
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
            lines.append(f"  [{format_path(err.field_path)}]  Missing environment variable '{err.var_name}'")
            if err.location is not None:
                lines.extend(format_location(err.location))
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
