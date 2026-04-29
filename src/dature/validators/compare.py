"""Comparison predicates: ``V >= x`` and ``V.len() >= n``."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, final

from dature.errors.exceptions import ValidatorTypeError
from dature.validators.predicate import Predicate
from dature.validators.type_compat import format_type, supports_len

CompareOp = Literal["gt", "ge", "lt", "le", "eq", "ne"]


_COMPARE_TEMPLATES: dict[CompareOp, str] = {
    "gt": "Value must be greater than {value}",
    "ge": "Value must be greater than or equal to {value}",
    "lt": "Value must be less than {value}",
    "le": "Value must be less than or equal to {value}",
    "eq": "Value must be equal to {value}",
    "ne": "Value must not be equal to {value}",
}


_LENGTH_TEMPLATES: dict[CompareOp, str] = {
    "gt": "Value length must be greater than {value}",
    "ge": "Value length must be greater than or equal to {value}",
    "lt": "Value length must be less than {value}",
    "le": "Value length must be less than or equal to {value}",
    "eq": "Value length must be equal to {value}",
    "ne": "Value length must not be equal to {value}",
}


@final
@dataclass(frozen=True, slots=True)
class ComparePredicate(Predicate):
    op: CompareOp
    value: Any
    error_message: str | None = field(default=None, kw_only=True)

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401, ARG002
        # No eager check — every Python object supports comparison dunders through `object`,
        # and strings compare lexicographically (so `V >= "a"` on str is legitimate).
        # Runtime mismatch is surfaced by adaptix.
        return

    def get_validator_func(self) -> Callable[[Any], bool]:
        op = self.op
        value = self.value
        if op == "gt":
            return lambda v: v > value
        if op == "ge":
            return lambda v: v >= value
        if op == "lt":
            return lambda v: v < value
        if op == "le":
            return lambda v: v <= value
        if op == "eq":
            return lambda v: v == value
        return lambda v: v != value

    def get_error_message(self) -> str:
        if self.error_message is not None:
            return self.error_message
        return _COMPARE_TEMPLATES[self.op].format(value=self.value)


@final
@dataclass(frozen=True, slots=True)
class LengthComparePredicate(Predicate):
    op: CompareOp
    value: int
    error_message: str | None = field(default=None, kw_only=True)

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401
        if not supports_len(field_type):
            path = ".".join(field_path) or "<root>"
            msg = (
                f"V.len() cannot be applied to field '{path}' (type {format_type(field_type)}) — "
                "field type must implement collections.abc.Sized "
                "(str, bytes, list, tuple, set, frozenset, dict, ...)"
            )
            raise ValidatorTypeError(field_path=field_path, message=msg)

    def get_validator_func(self) -> Callable[[Any], bool]:
        op = self.op
        value = self.value
        if op == "gt":
            return lambda v: len(v) > value
        if op == "ge":
            return lambda v: len(v) >= value
        if op == "lt":
            return lambda v: len(v) < value
        if op == "le":
            return lambda v: len(v) <= value
        if op == "eq":
            return lambda v: len(v) == value
        return lambda v: len(v) != value

    def get_error_message(self) -> str:
        if self.error_message is not None:
            return self.error_message
        return _LENGTH_TEMPLATES[self.op].format(value=self.value)
