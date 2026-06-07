"""When DSL — entry point for conditional source conditions.

Condition types:

- :class:`Match` — leaf: expands a template and checks membership
- :class:`AndCondition` — both sub-conditions must be true
- :class:`OrCondition` — at least one sub-condition must be true
- :class:`NotCondition` — negates a sub-condition

Build conditions via the :class:`When` entry point:

Example:
    >>> from dature import When
    >>> # simple equality
    >>> c = When("${APP_ENV}") == "prod"
    >>> # OR two different keys
    >>> c = (When("${APP_ENV}") == "prod") | (When("${APP_ENV}") == "staging")
    >>> # NOT
    >>> c = ~(When("${APP_ENV}") == "prod")
    >>> # AND across keys
    >>> c = (When("${APP_ENV}") == "prod") & When("${REGION}").in_("eu", "us")
"""

import abc
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, final

from dature.expansion.cross_source import find_refs, needs_cross_ref_expansion


def _reject_when_value(value: Any, context: str) -> None:  # noqa: ANN401
    """Block When(...) == When(...)-style mistakes at construction time."""
    if isinstance(value, (_When, Condition)):
        msg = (
            f"{context}: got a When-DSL object as a value. "
            "Use `When(template) <op> <literal>`, not `When(...) <op> When(...)`."
        )
        raise TypeError(msg)


class Condition(abc.ABC):
    """Base class for all When-DSL conditions."""

    @abc.abstractmethod
    def evaluate(self, expand: Callable[[str], str]) -> bool:
        """Return True if the condition is satisfied.

        Args:
            expand: A callable that expands template strings (env vars, cross-refs).
        """

    @abc.abstractmethod
    def ref_tags(self) -> set[str]:
        """Return all cross-source tag names referenced in this condition's templates."""

    @abc.abstractmethod
    def has_cross_refs(self) -> bool:
        """Return True if any leaf template contains a ``${@tag.key}`` cross-ref."""

    def __and__(self, other: "Condition") -> "AndCondition":
        if not isinstance(other, Condition):
            msg = f"Cannot combine condition with {type(other).__name__}"
            raise TypeError(msg)
        return AndCondition(self, other)

    def __or__(self, other: "Condition") -> "OrCondition":
        if not isinstance(other, Condition):
            msg = f"Cannot combine condition with {type(other).__name__}"
            raise TypeError(msg)
        return OrCondition(self, other)

    def __invert__(self) -> "NotCondition":
        return NotCondition(self)


@final
@dataclass(frozen=True, slots=True)
class Match(Condition):
    """Leaf condition: expand *template* and check membership in *expected*."""

    template: str
    expected: tuple[str, ...]

    def evaluate(self, expand: Callable[[str], str]) -> bool:
        return expand(self.template) in self.expected

    def ref_tags(self) -> set[str]:
        return {tag for tag, _ in find_refs(self.template)}

    def has_cross_refs(self) -> bool:
        return needs_cross_ref_expansion(self.template)


@final
@dataclass(frozen=True, slots=True)
class AndCondition(Condition):
    left: Condition
    right: Condition

    def evaluate(self, expand: Callable[[str], str]) -> bool:
        return self.left.evaluate(expand) and self.right.evaluate(expand)

    def ref_tags(self) -> set[str]:
        return self.left.ref_tags() | self.right.ref_tags()

    def has_cross_refs(self) -> bool:
        return self.left.has_cross_refs() or self.right.has_cross_refs()


@final
@dataclass(frozen=True, slots=True)
class OrCondition(Condition):
    left: Condition
    right: Condition

    def evaluate(self, expand: Callable[[str], str]) -> bool:
        return self.left.evaluate(expand) or self.right.evaluate(expand)

    def ref_tags(self) -> set[str]:
        return self.left.ref_tags() | self.right.ref_tags()

    def has_cross_refs(self) -> bool:
        return self.left.has_cross_refs() or self.right.has_cross_refs()


@final
@dataclass(frozen=True, slots=True)
class NotCondition(Condition):
    inner: Condition

    def evaluate(self, expand: Callable[[str], str]) -> bool:
        return not self.inner.evaluate(expand)

    def ref_tags(self) -> set[str]:
        return self.inner.ref_tags()

    def has_cross_refs(self) -> bool:
        return self.inner.has_cross_refs()


class _When:
    """Holds a template string; use operators to build a :class:`Condition`."""

    __slots__ = ("_template",)

    def __init__(self, template: str) -> None:
        self._template = template

    def __eq__(self, value: object) -> Match:  # type: ignore[override]
        _reject_when_value(value, f"When({self._template!r}) ==")
        if not isinstance(value, str):
            msg = f"When({self._template!r}) == expects a str, got {type(value).__name__}"
            raise TypeError(msg)
        return Match(self._template, (value,))

    def __ne__(self, value: object) -> NotCondition:  # type: ignore[override]
        _reject_when_value(value, f"When({self._template!r}) !=")
        if not isinstance(value, str):
            msg = f"When({self._template!r}) != expects a str, got {type(value).__name__}"
            raise TypeError(msg)
        return NotCondition(Match(self._template, (value,)))

    def in_(self, *values: str) -> Match:
        """Return a condition that passes when the template expands to any of *values*."""
        if not values:
            msg = f"When({self._template!r}).in_() requires at least one value"
            raise TypeError(msg)
        for v in values:
            _reject_when_value(v, f"When({self._template!r}).in_(...)")
            if not isinstance(v, str):
                msg = f"When({self._template!r}).in_() expects str values, got {type(v).__name__}"
                raise TypeError(msg)
        return Match(self._template, tuple(values))

    def not_in(self, *values: str) -> NotCondition:
        """Return a condition that passes when the template does NOT expand to any of *values*."""
        return NotCondition(self.in_(*values))

    __hash__ = None  # type: ignore[assignment]


def When(template: str) -> _When:  # noqa: N802
    """Entry point for the When-DSL.

    Args:
        template: A template string, e.g. ``"${APP_ENV}"`` or ``"${@cfg.env}"``.

    Returns:
        A :class:`_When` object; apply ``==``, ``!=``, ``.in_(...)``, ``.not_in(...)``
        to produce a :class:`Condition`.
    """
    if not isinstance(template, str):
        msg = f"When() expects a str template, got {type(template).__name__}"
        raise TypeError(msg)
    return _When(template)
