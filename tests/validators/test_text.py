"""Unit tests for ``MatchesPredicate``."""

from typing import assert_type

from dature import V
from dature.validators.text import MatchesPredicate


class TestStaticTyping:
    """Static-only assertions — the checked behavior is verified by mypy/pyright, not at runtime."""

    def test_matches_returns_matches_predicate(self) -> None:
        assert_type(V.matches(r"^[a-z]+$"), MatchesPredicate)


class TestMatchesRuntime:
    def test_matches(self) -> None:
        func = V.matches(r"^[a-z]+$").get_validator_func()
        assert func("abc") is True
        assert func("") is False
        assert func("ABC") is False
        assert func("abc123") is False


class TestMatchesErrorMessage:
    def test_default_message(self) -> None:
        assert V.matches(r"^\w+$").get_error_message() == r"Value must match pattern '^\w+$'"

    def test_override_via_kwarg(self) -> None:
        assert V.matches(r"^x$", error_message="not x").get_error_message() == "not x"
