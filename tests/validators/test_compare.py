"""Unit tests for ``ComparePredicate`` / ``LengthComparePredicate`` — construction and runtime."""

import pytest

from dature import V
from dature.validators.compare import ComparePredicate, LengthComparePredicate
from dature.validators.predicate import Predicate


class TestCompareConstruction:
    @pytest.mark.parametrize(
        ("expr", "op", "value"),
        [
            (V >= 1, "ge", 1),
            (V > 1, "gt", 1),
            (V <= 10, "le", 10),
            (V < 10, "lt", 10),
            (V == "a", "eq", "a"),
            (V != 0, "ne", 0),
        ],
    )
    def test_operator_builds_compare_predicate(self, expr: Predicate, op: str, value: object) -> None:
        assert isinstance(expr, ComparePredicate)
        assert expr.op == op
        assert expr.value == value


class TestCompareRuntime:
    @pytest.mark.parametrize(
        ("predicate", "good", "bad"),
        [
            (V >= 1, [1, 5, 100], [0, -1]),
            (V > 1, [2, 100], [1, 0, -1]),
            (V <= 10, [10, 0, -5], [11, 100]),
            (V < 10, [9, 0], [10, 11]),
            (V == "admin", ["admin"], ["user", "", "ADMIN"]),
            (V != "admin", ["user", ""], ["admin"]),
        ],
    )
    def test_validator_func(self, predicate: Predicate, good: list[object], bad: list[object]) -> None:
        func = predicate.get_validator_func()
        for g in good:
            assert func(g) is True
        for b in bad:
            assert func(b) is False


class TestCompareErrorMessage:
    @pytest.mark.parametrize(
        ("predicate", "expected"),
        [
            (V >= 1, "Value must be greater than or equal to 1"),
            (V > 1, "Value must be greater than 1"),
            (V <= 10, "Value must be less than or equal to 10"),
            (V < 10, "Value must be less than 10"),
            (V == "admin", "Value must be equal to admin"),
            (V != 0, "Value must not be equal to 0"),
        ],
    )
    def test_default_message(self, predicate: Predicate, expected: str) -> None:
        assert predicate.get_error_message() == expected

    def test_override_via_constructor(self) -> None:
        pred = ComparePredicate("ge", 1, error_message="custom message")
        assert pred.get_error_message() == "custom message"

    def test_override_via_with_error_message(self) -> None:
        pred = (V >= 18).with_error_message("Age must be 18 or older")
        assert pred.get_error_message() == "Age must be 18 or older"


class TestLengthCompareConstruction:
    @pytest.mark.parametrize(
        ("predicate", "op", "value"),
        [
            (V.len() >= 3, "ge", 3),
            (V.len() > 3, "gt", 3),
            (V.len() <= 5, "le", 5),
            (V.len() < 5, "lt", 5),
            (V.len() == 4, "eq", 4),
            (V.len() != 0, "ne", 0),
        ],
    )
    def test_construction(self, predicate: Predicate, op: str, value: int) -> None:
        assert isinstance(predicate, LengthComparePredicate)
        assert predicate.op == op
        assert predicate.value == value


class TestLengthCompareRuntime:
    @pytest.mark.parametrize(
        ("predicate", "good", "bad"),
        [
            (V.len() >= 3, ["abc", "abcd", [1, 2, 3]], ["", "ab", [1]]),
            (V.len() <= 5, ["", "abc", "abcde"], ["abcdef", [1, 2, 3, 4, 5, 6]]),
        ],
    )
    def test_validator_func(self, predicate: Predicate, good: list[object], bad: list[object]) -> None:
        func = predicate.get_validator_func()
        for g in good:
            assert func(g) is True
        for b in bad:
            assert func(b) is False


class TestLengthCompareErrorMessage:
    @pytest.mark.parametrize(
        ("predicate", "expected"),
        [
            (V.len() >= 3, "Value length must be greater than or equal to 3"),
            (V.len() > 3, "Value length must be greater than 3"),
            (V.len() <= 5, "Value length must be less than or equal to 5"),
            (V.len() < 5, "Value length must be less than 5"),
        ],
    )
    def test_default_message(self, predicate: Predicate, expected: str) -> None:
        assert predicate.get_error_message() == expected

    def test_override_via_constructor(self) -> None:
        pred = LengthComparePredicate("ge", 3, error_message="too short")
        assert pred.get_error_message() == "too short"
