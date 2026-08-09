from collections.abc import Sequence
from types import TracebackType
from typing import Self

from dature.errors.loc_types import SourceLocation
from dature.errors.rendering import format_location, format_path
from dature.errors.traceback_trim import user_frames_only
from dature.type_aliases import JSONValue


class DatureError(Exception):
    """Base dature error."""

    @property
    def __traceback__(self) -> TracebackType | None:
        """Traceback with dature's own frames stripped, so only caller frames show."""
        return user_frames_only(super().__traceback__)

    @__traceback__.setter
    def __traceback__(self, value: TracebackType | None) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        super().with_traceback(value)


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


class DatureErrorGroup(ExceptionGroup[DatureError]):
    """Base for dature exception groups; subclasses add domain-specific context."""

    @property
    def __traceback__(self) -> TracebackType | None:
        """Traceback with dature's own frames stripped, so only caller frames show."""
        return user_frames_only(super().__traceback__)

    @__traceback__.setter
    def __traceback__(self, value: TracebackType | None) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        super().with_traceback(value)

    def derive(self, excs: "Sequence[DatureError]", /) -> "Self":  # type: ignore[override]
        return self.__class__(self.args[0], list(excs))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self)!r}, {list(self.exceptions)!r})"


class DatureConfigError(DatureErrorGroup):
    dataclass_name: str

    def __init__(
        self,
        dataclass_name: str,
        _errors: Sequence[DatureError | BaseException],
    ) -> None:
        self.dataclass_name = dataclass_name

    def derive(self, excs: Sequence[DatureError], /) -> Self:  # type: ignore[override]
        return self.__class__(self.dataclass_name, list(excs))

    def __str__(self) -> str:
        return f"{self.dataclass_name} loading errors ({len(self.exceptions)})"


class EnvVarExpandError(DatureErrorGroup):
    def __str__(self) -> str:
        return self._format(f"Missing environment variables ({len(self.exceptions)})")

    def _format(self, header: str) -> str:
        lines: list[str] = [header, ""]
        for err in self.exceptions:
            if not isinstance(err, MissingEnvVarError):
                continue
            lines.append(f"  [{format_path(err.field_path)}]  Missing environment variable '{err.var_name}'")
            if err.location is not None:
                lines.extend(format_location(err.location))
            lines.append("")
        return "\n".join(lines)


class ConfigEnvVarExpandError(EnvVarExpandError, DatureConfigError):
    def __str__(self) -> str:
        return self._format(f"{self.dataclass_name} env expand errors ({len(self.exceptions)})")


class MergeConflictError(DatureConfigError):
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
    def __str__(self) -> str:
        return f"{self.dataclass_name} field group errors ({len(self.exceptions)})"


class CrossRefError(DatureError):
    def __init__(
        self,
        *,
        ref: str,
        message: str,
        field_path: list[str] | None = None,
    ) -> None:
        self.ref = ref
        self.message = message
        self.field_path = field_path or []
        super().__init__(message)


class CrossRefExpandError(DatureErrorGroup):
    def __str__(self) -> str:
        lines: list[str] = [f"Cross-source reference errors ({len(self.exceptions)})", ""]
        for err in self.exceptions:
            if not isinstance(err, CrossRefError):
                continue
            path_str = format_path(err.field_path) if err.field_path else ""
            prefix = f"  [{path_str}]  " if path_str else "  "
            lines.append(f"{prefix}{err.ref!r}: {err.message}")
            lines.append("")
        return "\n".join(lines)
