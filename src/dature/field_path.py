from contextlib import suppress
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, TypeVar, final, get_type_hints, overload

from dature.protocols import DataclassInstance

T = TypeVar("T")


def resolve_nested_owner(
    owner: type[DataclassInstance],
    parts: tuple[str, ...],
) -> type[DataclassInstance]:
    """Walk type hints from owner through intermediate parts to find the leaf owner type."""
    current: type = owner
    for part in parts:
        hints = get_type_hints(current)
        if part not in hints:
            msg = f"Type '{current.__name__}' has no field '{part}'"
            raise TypeError(msg)
        current = hints[part]
        if not is_dataclass(current):
            msg = f"Intermediate field '{part}' of type '{current}' is not a dataclass"
            raise TypeError(msg)
    return current


def resolve_field_type(
    owner: type[DataclassInstance],
    parts: tuple[str, ...],
) -> type[DataclassInstance] | None:
    """Walk the field chain and return the type of the last field, or None if not a dataclass."""
    with suppress(TypeError):
        return resolve_nested_owner(owner, parts)
    return None


def _validate_field(owner: type[DataclassInstance], parts: tuple[str, ...], name: str) -> None:
    if not parts:
        target = owner
    else:
        resolved = resolve_field_type(owner, parts)
        if resolved is None:
            return
        target = resolved

    field_names = {f.name for f in fields(target)}
    if name not in field_names:
        msg = f"'{target.__name__}' has no field '{name}'"
        raise AttributeError(msg)


# --8<-- [start:field-path]
@dataclass(frozen=True, slots=True)
class FieldPath:
    owner: type[DataclassInstance] | str
    parts: tuple[str, ...] = ()

    def __getattr__(self, name: str) -> "FieldPath":
        if isinstance(self.owner, type):
            _validate_field(self.owner, self.parts, name)
        return FieldPath(owner=self.owner, parts=(*self.parts, name))

    def as_path(self) -> str:
        if not self.parts:
            msg = "FieldPath must contain at least one field name"
            raise ValueError(msg)
        return ".".join(self.parts)


# --8<-- [end:field-path]


def _validate_field_path_parts(field_path: FieldPath, schema: type[DataclassInstance]) -> None:
    for i, part in enumerate(field_path.parts):
        _validate_field(schema, field_path.parts[:i], part)


def validate_field_path_owner(field_path: FieldPath, schema: type[DataclassInstance]) -> None:
    if isinstance(field_path.owner, str):
        if field_path.owner != schema.__name__:
            msg = f"FieldPath owner '{field_path.owner}' does not match target dataclass '{schema.__name__}'"
            raise TypeError(msg)
        _validate_field_path_parts(field_path, schema)
        return
    if field_path.owner is not schema:
        msg = f"FieldPath owner '{field_path.owner.__name__}' does not match target dataclass '{schema.__name__}'"
        raise TypeError(msg)


def extract_field_path(predicate: Any, schema: type[DataclassInstance] | None = None) -> str:  # noqa: ANN401
    if not isinstance(predicate, FieldPath):
        msg = f"Expected FieldPath, got {type(predicate).__name__}"
        raise TypeError(msg)
    if schema is not None:
        validate_field_path_owner(predicate, schema)
    return predicate.as_path()


@final
class FieldAny:
    """Sentinel ``F.ANY`` — skip every invalid field (see ``skip_field_if_invalid``)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "F.ANY"


_ANY = FieldAny()


# --8<-- [start:field-path-factory]
class _FieldPathFactory:
    @overload
    def __getitem__(self, owner: type[T]) -> T: ...

    @overload
    def __getitem__(self, owner: str) -> FieldPath: ...

    def __getitem__(self, owner: type[Any] | str) -> Any:
        if isinstance(owner, type) and not is_dataclass(owner):
            msg = f"'{owner.__name__}' is not a dataclass"
            raise TypeError(msg)
        return FieldPath(owner=owner)

    @property
    def ANY(self) -> FieldAny:  # noqa: N802 -- constant-style name, mirrors adaptix's P.ANY
        """Sentinel meaning "skip every invalid field" for ``skip_field_if_invalid``."""
        return _ANY


F = _FieldPathFactory()
# --8<-- [end:field-path-factory]


class Absolute(str):
    """Alias matched against the raw source key as-is — the source ``prefix`` is ignored."""

    __slots__ = ()
