"""Tests for field-level merge strategy classes (batch reducers)."""

import pytest

from dature.strategies.field import (
    FieldAppend,
    FieldAppendUnique,
    FieldFirstWins,
    FieldLastWins,
    FieldMergeStrategy,
    FieldPrepend,
    FieldPrependUnique,
)


class TestFieldFirstWins:
    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            pytest.param(["a", "b", "c"], "a", id="strings"),
            pytest.param([1, 2, 3], 1, id="ints"),
            pytest.param([{"x": 1}, {"y": 2}], {"x": 1}, id="dicts"),
            pytest.param([None, "a"], None, id="none_first"),
            pytest.param(["only"], "only", id="single_value"),
        ],
    )
    def test_returns_first(self, values, expected):
        assert FieldFirstWins()(values) == expected


class TestFieldLastWins:
    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            pytest.param(["a", "b", "c"], "c", id="strings"),
            pytest.param([1, 2, 3], 3, id="ints"),
            pytest.param([{"x": 1}, {"y": 2}], {"y": 2}, id="dicts"),
            pytest.param(["a", None], None, id="none_last"),
            pytest.param(["only"], "only", id="single_value"),
        ],
    )
    def test_returns_last(self, values, expected):
        assert FieldLastWins()(values) == expected


class TestFieldAppend:
    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            pytest.param([[1, 2], [3]], [1, 2, 3], id="two_lists"),
            pytest.param([[1], [2], [3]], [1, 2, 3], id="three_lists"),
            pytest.param([["a", "b"], ["a", "c"]], ["a", "b", "a", "c"], id="duplicates_kept"),
            pytest.param([[]], [], id="single_empty"),
            pytest.param([[1, 2]], [1, 2], id="single_value"),
        ],
    )
    def test_appends(self, values, expected):
        assert FieldAppend()(values) == expected

    def test_non_list_raises(self):
        with pytest.raises(TypeError, match="APPEND strategy requires every value to be a list"):
            FieldAppend()([[1, 2], "not-a-list"])


class TestFieldAppendUnique:
    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            pytest.param([[1, 2], [3]], [1, 2, 3], id="no_duplicates"),
            pytest.param([["a", "b"], ["a", "c"]], ["a", "b", "c"], id="dedup"),
            pytest.param([[1, 1], [1]], [1], id="all_same"),
        ],
    )
    def test_appends_unique(self, values, expected):
        assert FieldAppendUnique()(values) == expected


class TestFieldPrepend:
    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            pytest.param([[1, 2], [3]], [3, 1, 2], id="two_lists"),
            pytest.param([[1], [2], [3]], [3, 2, 1], id="three_lists_reversed"),
            pytest.param([["a"]], ["a"], id="single_value"),
        ],
    )
    def test_prepends(self, values, expected):
        assert FieldPrepend()(values) == expected


class TestFieldPrependUnique:
    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            pytest.param([[1, 2], [3]], [3, 1, 2], id="no_duplicates"),
            pytest.param([["a", "b"], ["a"]], ["a", "b"], id="dedup_after_reverse"),
        ],
    )
    def test_prepends_unique(self, values, expected):
        assert FieldPrependUnique()(values) == expected


class TestProtocol:
    def test_callable_satisfies_protocol(self):
        def my_reducer(values):
            return sum(values)

        # Plain callable is structurally compatible with FieldMergeStrategy.
        assert isinstance(my_reducer, FieldMergeStrategy)

    def test_custom_class_satisfies_protocol(self):
        class TakeMax:
            def __call__(self, values):
                return max(values)

        strategy = TakeMax()
        assert isinstance(strategy, FieldMergeStrategy)
        assert strategy([3, 1, 2]) == 3
