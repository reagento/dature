"""Unit tests for boolean composition of predicates: ``&``, ``|``, ``~``."""

import pytest

from dature import V
from dature.validators.predicate import AndPredicate, NotPredicate, OrPredicate


class TestAnd:
    def test_construction_and_runtime(self) -> None:
        pred = (V >= 1) & (V <= 10)
        assert isinstance(pred, AndPredicate)
        func = pred.get_validator_func()
        assert func(5) is True
        assert func(1) is True
        assert func(10) is True
        assert func(0) is False
        assert func(11) is False


class TestOr:
    def test_construction_and_runtime(self) -> None:
        pred = (V == "admin") | (V == "root")
        assert isinstance(pred, OrPredicate)
        func = pred.get_validator_func()
        assert func("admin") is True
        assert func("root") is True
        assert func("user") is False

    def test_error_message(self) -> None:
        msg = ((V == "a") | (V == "b")).get_error_message()
        assert "or" in msg
        assert "must be equal to a" in msg
        assert "must be equal to b" in msg


class TestNot:
    def test_construction_and_runtime(self) -> None:
        pred = ~(V == "admin")
        assert isinstance(pred, NotPredicate)
        func = pred.get_validator_func()
        assert func("user") is True
        assert func("admin") is False

    def test_error_message(self) -> None:
        msg = (~(V == "x")).get_error_message()
        assert msg.startswith("NOT (")
        assert "must be equal to x" in msg


class TestCombinedComposition:
    def test_and_with_matches(self) -> None:
        pred = ((V.len() >= 3) & (V.len() <= 10)) & V.matches(r"^[a-z]+$")
        func = pred.get_validator_func()
        assert func("abc") is True
        assert func("abcdefghij") is True
        assert func("ab") is False
        assert func("abcdefghijk") is False
        assert func("Abc") is False


class TestComposeWithNonPredicate:
    def test_and_rejects_non_predicate(self) -> None:
        with pytest.raises(TypeError):
            _ = (V >= 1) & "not a predicate"  # type: ignore[operator]

    def test_or_rejects_non_predicate(self) -> None:
        with pytest.raises(TypeError):
            _ = (V >= 1) | 42  # type: ignore[operator]
