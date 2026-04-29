"""Unit tests for collection predicates: ``V.in_``, ``V.unique_items``, ``V.each``."""

import pytest

from dature import V
from dature.validators.collection import EachPredicate, InPredicate


class TestIn:
    def test_construction(self) -> None:
        pred = V.in_(("a", "b", "c"))
        assert isinstance(pred, InPredicate)
        assert pred.values == ("a", "b", "c")

    def test_accepts_any_iterable(self) -> None:
        pred = V.in_(iter(["a", "b"]))
        assert pred.values == ("a", "b")

    def test_runtime(self) -> None:
        func = V.in_(("admin", "user")).get_validator_func()
        assert func("admin") is True
        assert func("user") is True
        assert func("guest") is False

    def test_default_message(self) -> None:
        assert V.in_(("a", "b")).get_error_message() == "Value must be one of: 'a', 'b'"

    def test_override_via_kwarg(self) -> None:
        assert V.in_(("a", "b"), error_message="bad value").get_error_message() == "bad value"


class TestUniqueItems:
    def test_runtime(self) -> None:
        func = V.unique_items().get_validator_func()
        assert func([]) is True
        assert func([1]) is True
        assert func([1, 2, 3]) is True
        assert func([1, 1]) is False
        assert func([1, 2, 1]) is False

    def test_default_message(self) -> None:
        assert V.unique_items().get_error_message() == "Value must contain unique items"

    def test_override_via_kwarg(self) -> None:
        assert V.unique_items(error_message="dup").get_error_message() == "dup"


class TestEach:
    def test_construction(self) -> None:
        inner = V.len() >= 3
        pred = V.each(inner)
        assert isinstance(pred, EachPredicate)
        assert pred.inner is inner

    def test_runtime(self) -> None:
        func = V.each(V.len() >= 3).get_validator_func()
        assert func([]) is True
        assert func(["abc", "abcd"]) is True
        assert func(["ab", "abc"]) is False
        assert func(["abc", "ab", "abcd"]) is False

    def test_composed_inner(self) -> None:
        inner = (V.len() >= 2) & V.matches(r"^[a-z]+$")
        func = V.each(inner).get_validator_func()
        assert func(["ab", "cde"]) is True
        assert func(["a", "bc"]) is False
        assert func(["Ab", "cd"]) is False

    def test_rejects_non_predicate(self) -> None:
        with pytest.raises(TypeError, match=r"V\.each"):
            V.each("not a predicate")

    def test_default_message_delegates_to_inner(self) -> None:
        pred = V.each(V.len() >= 3)
        assert pred.get_error_message() == (V.len() >= 3).get_error_message()

    def test_override_via_kwarg(self) -> None:
        assert V.each(V.len() >= 3, error_message="elem too short").get_error_message() == "elem too short"
