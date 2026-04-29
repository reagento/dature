"""V DSL — entry point for declarative validation predicates.

Predicate types themselves live in sibling modules:

- :mod:`dature.validators.predicate` — ``Predicate`` ABC, ``And/Or/Not``
- :mod:`dature.validators.compare` — ``Compare``, ``LengthCompare``
- :mod:`dature.validators.text` — ``Matches``
- :mod:`dature.validators.collection` — ``In``, ``UniqueItems``, ``Each``
- :mod:`dature.validators.custom` — ``Custom`` (``V.check`` escape hatch)
- :mod:`dature.validators.root` — ``RootPredicate`` (``V.root``)

This module only assembles the ``V`` singleton: the entry-point that the user
actually writes in their schemas, and the ``_LengthAccessor`` returned by
``V.len()``.

Example:
    >>> from dataclasses import dataclass
    >>> from typing import Annotated
    >>> from dature import V
    >>>
    >>> @dataclass
    ... class ServiceConfig:
    ...     port: Annotated[int, (V >= 1) & (V <= 65535)]
    ...     name: Annotated[str, (V.len() >= 3) & (V.len() <= 50)]
    ...     tags: Annotated[list[str], V.unique_items() & V.each(V.len() >= 3)]

Chained comparisons like ``3 <= V.len() <= 10`` are not supported — Python evaluates
them as ``(3 <= V.len()) and (V.len() <= 10)``, and ``and`` would collapse the two
halves into one. Use ``(V.len() >= 3) & (V.len() <= 10)`` instead.
"""

from collections.abc import Callable, Iterable
from typing import Any, final

from dature.validators.collection import EachPredicate, InPredicate, UniqueItemsPredicate
from dature.validators.compare import ComparePredicate, LengthComparePredicate
from dature.validators.custom import CustomPredicate
from dature.validators.predicate import Predicate
from dature.validators.root import RootPredicate
from dature.validators.text import MatchesPredicate


def _reject_dsl_value(value: Any, context: str) -> None:  # noqa: ANN401
    """Block ``V == V``-style mistakes at construction time with a clear message."""
    if isinstance(value, (_V, _LengthAccessor, Predicate, RootPredicate)):
        msg = f"{context}: got a V-DSL object as a value. Use `V <op> <concrete_value>`, not `V <op> V`."
        raise TypeError(msg)


@final
class _LengthAccessor:
    """Returned by ``V.len()``. Supports comparison operators to build LengthComparePredicate."""

    __slots__ = ()

    def __ge__(self, value: int) -> LengthComparePredicate:
        _reject_dsl_value(value, "V.len() >=")
        return LengthComparePredicate("ge", value)

    def __gt__(self, value: int) -> LengthComparePredicate:
        _reject_dsl_value(value, "V.len() >")
        return LengthComparePredicate("gt", value)

    def __le__(self, value: int) -> LengthComparePredicate:
        _reject_dsl_value(value, "V.len() <=")
        return LengthComparePredicate("le", value)

    def __lt__(self, value: int) -> LengthComparePredicate:
        _reject_dsl_value(value, "V.len() <")
        return LengthComparePredicate("lt", value)

    def __eq__(self, value: object) -> LengthComparePredicate:  # type: ignore[override]
        _reject_dsl_value(value, "V.len() ==")
        return LengthComparePredicate("eq", value)  # type: ignore[arg-type]

    def __ne__(self, value: object) -> LengthComparePredicate:  # type: ignore[override]
        _reject_dsl_value(value, "V.len() !=")
        return LengthComparePredicate("ne", value)  # type: ignore[arg-type]

    __hash__ = None  # type: ignore[assignment]


class _V:
    """Singleton value-placeholder. Use the module-level ``V`` instance."""

    __slots__ = ()

    def __ge__(self, value: Any) -> ComparePredicate:  # noqa: ANN401
        _reject_dsl_value(value, "V >=")
        return ComparePredicate("ge", value)

    def __gt__(self, value: Any) -> ComparePredicate:  # noqa: ANN401
        _reject_dsl_value(value, "V >")
        return ComparePredicate("gt", value)

    def __le__(self, value: Any) -> ComparePredicate:  # noqa: ANN401
        _reject_dsl_value(value, "V <=")
        return ComparePredicate("le", value)

    def __lt__(self, value: Any) -> ComparePredicate:  # noqa: ANN401
        _reject_dsl_value(value, "V <")
        return ComparePredicate("lt", value)

    def __eq__(self, value: object) -> ComparePredicate:  # type: ignore[override]
        _reject_dsl_value(value, "V ==")
        return ComparePredicate("eq", value)

    def __ne__(self, value: object) -> ComparePredicate:  # type: ignore[override]
        _reject_dsl_value(value, "V !=")
        return ComparePredicate("ne", value)

    __hash__ = None  # type: ignore[assignment]

    def len(self) -> _LengthAccessor:
        return _LengthAccessor()

    def in_(self, values: Iterable[Any], *, error_message: str | None = None) -> InPredicate:
        return InPredicate(tuple(values), error_message=error_message)

    def matches(self, pattern: str, *, error_message: str | None = None) -> MatchesPredicate:
        return MatchesPredicate(pattern, error_message=error_message)

    def unique_items(self, *, error_message: str | None = None) -> UniqueItemsPredicate:
        return UniqueItemsPredicate(error_message=error_message)

    def each(self, inner: Predicate, *, error_message: str | None = None) -> EachPredicate:
        if not isinstance(inner, Predicate):
            msg = f"V.each(...) expects a Predicate, got {type(inner).__name__}"
            raise TypeError(msg)
        return EachPredicate(inner, error_message=error_message)

    def check(self, func: Callable[[Any], bool], *, error_message: str) -> CustomPredicate:
        return CustomPredicate(func, error_message)

    @staticmethod
    def root(
        func: Callable[..., bool],
        *,
        error_message: str = "Root validation failed",
    ) -> RootPredicate:
        return RootPredicate(func, error_message)


V = _V()
