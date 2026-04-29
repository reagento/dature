"""Collection predicates: ``V.in_(...)``, ``V.unique_items()``, ``V.each(inner)``."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, final

from dature.errors.exceptions import ValidatorTypeError
from dature.validators.predicate import Predicate
from dature.validators.type_compat import (
    element_type_of,
    format_type,
    supports_collection,
    supports_iteration,
)


@final
@dataclass(frozen=True, slots=True)
class InPredicate(Predicate):
    values: tuple[Any, ...]
    error_message: str | None = field(default=None, kw_only=True)

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401, ARG002
        # Type-erased — adaptix will reject values that don't coerce to the right type.
        return

    def get_validator_func(self) -> Callable[[Any], bool]:
        values = self.values
        return lambda v: v in values

    def get_error_message(self) -> str:
        if self.error_message is not None:
            return self.error_message
        rendered = ", ".join(repr(v) for v in self.values)
        return f"Value must be one of: {rendered}"


@final
@dataclass(frozen=True, slots=True)
class UniqueItemsPredicate(Predicate):
    error_message: str | None = field(default=None, kw_only=True)

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401
        if not supports_collection(field_type):
            path = ".".join(field_path) or "<root>"
            msg = (
                f"V.unique_items() cannot be applied to field '{path}' "
                f"(type {format_type(field_type)}) — "
                "field must implement collections.abc.Collection "
                "(list, tuple, set, frozenset, ...)"
            )
            raise ValidatorTypeError(field_path=field_path, message=msg)

    def get_validator_func(self) -> Callable[[Any], bool]:
        def validate(val: Any) -> bool:  # noqa: ANN401
            return len(val) == len(set(val))

        return validate

    def get_error_message(self) -> str:
        if self.error_message is not None:
            return self.error_message
        return "Value must contain unique items"


@final
@dataclass(frozen=True, slots=True)
class EachPredicate(Predicate):
    inner: Predicate
    error_message: str | None = field(default=None, kw_only=True)

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401
        if not supports_iteration(field_type):
            path = ".".join(field_path) or "<root>"
            msg = (
                f"V.each(...) cannot be applied to field '{path}' "
                f"(type {format_type(field_type)}) — "
                "field must implement collections.abc.Iterable "
                "(list, tuple, set, frozenset, ...)"
            )
            raise ValidatorTypeError(field_path=field_path, message=msg)
        self.inner.check_type(element_type_of(field_type), field_path=field_path)

    def get_validator_func(self) -> Callable[[Any], bool]:
        inner_func = self.inner.get_validator_func()

        def validate(val: Any) -> bool:  # noqa: ANN401
            return all(inner_func(elem) for elem in val)

        return validate

    def get_error_message(self) -> str:
        if self.error_message is not None:
            return self.error_message
        return self.inner.get_error_message()
