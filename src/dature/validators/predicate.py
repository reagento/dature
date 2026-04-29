"""Base ``Predicate`` class and boolean composition (And / Or / Not).

Every leaf predicate in the V DSL subclasses :class:`Predicate`. The three
composition primitives live here too because they are mutually recursive with
the base class — ``__and__`` / ``__or__`` / ``__invert__`` on ``Predicate``
construct these classes directly.
"""

import abc
import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, final


class Predicate(abc.ABC):
    """Base class for all V-predicates. Subclasses must be frozen dataclasses."""

    @abc.abstractmethod
    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401
        """Raise ``ValidatorTypeError`` if this predicate cannot be applied to ``field_type``."""

    @abc.abstractmethod
    def get_validator_func(self) -> Callable[[Any], bool]:
        """Return a callable that takes the field value and returns True if valid."""

    @abc.abstractmethod
    def get_error_message(self) -> str:
        """Return the default error message shown when the value fails this predicate."""

    def __and__(self, other: "Predicate") -> "AndPredicate":
        if not isinstance(other, Predicate):
            msg = f"Cannot combine predicate with {type(other).__name__}"
            raise TypeError(msg)
        return AndPredicate(self, other)

    def __or__(self, other: "Predicate") -> "OrPredicate":
        if not isinstance(other, Predicate):
            msg = f"Cannot combine predicate with {type(other).__name__}"
            raise TypeError(msg)
        return OrPredicate(self, other)

    def __invert__(self) -> "NotPredicate":
        return NotPredicate(self)

    def with_error_message(self, message: str) -> "Predicate":
        """Return a copy of this predicate with a custom error message.

        Supported on leaf predicates only — composite predicates (``&``, ``|``, ``~``)
        derive their message from their children and raise ``TypeError``.
        """
        try:
            return dataclasses.replace(self, error_message=message)  # type: ignore[type-var]
        except TypeError as exc:
            msg = (
                f"{type(self).__name__} does not support error_message override; override on individual leaf predicates"
            )
            raise TypeError(msg) from exc


@final
@dataclass(frozen=True, slots=True)
class AndPredicate(Predicate):
    left: Predicate
    right: Predicate

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401
        self.left.check_type(field_type, field_path=field_path)
        self.right.check_type(field_type, field_path=field_path)

    def get_validator_func(self) -> Callable[[Any], bool]:
        left_func = self.left.get_validator_func()
        right_func = self.right.get_validator_func()
        return lambda v: left_func(v) and right_func(v)

    def get_error_message(self) -> str:
        return f"{self.left.get_error_message()} and {self.right.get_error_message()}"


@final
@dataclass(frozen=True, slots=True)
class OrPredicate(Predicate):
    left: Predicate
    right: Predicate

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401
        self.left.check_type(field_type, field_path=field_path)
        self.right.check_type(field_type, field_path=field_path)

    def get_validator_func(self) -> Callable[[Any], bool]:
        left_func = self.left.get_validator_func()
        right_func = self.right.get_validator_func()
        return lambda v: left_func(v) or right_func(v)

    def get_error_message(self) -> str:
        return f"{self.left.get_error_message()} or {self.right.get_error_message()}"


@final
@dataclass(frozen=True, slots=True)
class NotPredicate(Predicate):
    inner: Predicate

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401
        self.inner.check_type(field_type, field_path=field_path)

    def get_validator_func(self) -> Callable[[Any], bool]:
        inner_func = self.inner.get_validator_func()
        return lambda v: not inner_func(v)

    def get_error_message(self) -> str:
        return f"NOT ({self.inner.get_error_message()})"
