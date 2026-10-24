"""Tests for field-level merge strategy classes (batch reducers)."""

import pytest

from dature.strategies.field import (
    FieldAppend,
    FieldAppendUnique,
    FieldFirstWins,
    FieldLastWins,
    FieldMergeResult,
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
        result = FieldFirstWins()(values)

        assert result == FieldMergeResult(value=expected, contributors=[0])


class TestFieldLastWins:
    @pytest.mark.parametrize(
        ("values", "expected", "contributors"),
        [
            pytest.param(["a", "b", "c"], "c", [2], id="strings"),
            pytest.param([1, 2, 3], 3, [2], id="ints"),
            pytest.param([{"x": 1}, {"y": 2}], {"y": 2}, [1], id="dicts"),
            pytest.param(["a", None], None, [1], id="none_last"),
            pytest.param(["only"], "only", [0], id="single_value"),
        ],
    )
    def test_returns_last(self, values, expected, contributors):
        result = FieldLastWins()(values)

        assert result == FieldMergeResult(value=expected, contributors=contributors)


class TestFieldAppend:
    @pytest.mark.parametrize(
        ("values", "expected", "contributors"),
        [
            pytest.param([[1, 2], [3]], [1, 2, 3], [0, 1], id="two_lists"),
            pytest.param([[1], [2], [3]], [1, 2, 3], [0, 1, 2], id="three_lists"),
            pytest.param([["a", "b"], ["a", "c"]], ["a", "b", "a", "c"], [0, 1], id="duplicates_kept"),
            pytest.param([[1], [], [2]], [1, 2], [0, 2], id="empty_chunk_skipped"),
            pytest.param([[], []], [], [0, 1], id="all_empty_fall_back_to_all"),
            pytest.param([[]], [], [0], id="single_empty"),
            pytest.param([[1, 2]], [1, 2], [0], id="single_value"),
        ],
    )
    def test_appends(self, values, expected, contributors):
        result = FieldAppend()(values)

        assert result == FieldMergeResult(value=expected, contributors=contributors)

    def test_non_list_raises(self):
        with pytest.raises(TypeError, match="APPEND strategy requires every value to be a list"):
            FieldAppend()([[1, 2], "not-a-list"])


class TestFieldAppendUnique:
    @pytest.mark.parametrize(
        ("values", "expected", "contributors"),
        [
            pytest.param([[1, 2], [3]], [1, 2, 3], [0, 1], id="no_duplicates"),
            pytest.param([["a", "b"], ["a", "c"]], ["a", "b", "c"], [0, 1], id="dedup"),
            pytest.param([[1, 1], [1]], [1], [0], id="all_same"),
            pytest.param([[1, 2], [2], [3]], [1, 2, 3], [0, 2], id="fully_deduplicated_chunk_skipped"),
            pytest.param([[], []], [], [0, 1], id="all_empty_fall_back_to_all"),
        ],
    )
    def test_appends_unique(self, values, expected, contributors):
        result = FieldAppendUnique()(values)

        assert result == FieldMergeResult(value=expected, contributors=contributors)


class TestFieldPrepend:
    @pytest.mark.parametrize(
        ("values", "expected", "contributors"),
        [
            pytest.param([[1, 2], [3]], [3, 1, 2], [0, 1], id="two_lists"),
            pytest.param([[1], [2], [3]], [3, 2, 1], [0, 1, 2], id="three_lists_reversed"),
            pytest.param([[1], [], [2]], [2, 1], [0, 2], id="empty_chunk_skipped"),
            pytest.param([["a"]], ["a"], [0], id="single_value"),
        ],
    )
    def test_prepends(self, values, expected, contributors):
        result = FieldPrepend()(values)

        assert result == FieldMergeResult(value=expected, contributors=contributors)


class TestFieldPrependUnique:
    @pytest.mark.parametrize(
        ("values", "expected", "contributors"),
        [
            pytest.param([[1, 2], [3]], [3, 1, 2], [0, 1], id="no_duplicates"),
            pytest.param([["a", "b"], ["a"]], ["a", "b"], [0, 1], id="dedup_after_reverse"),
            pytest.param([["a"], ["a", "b"]], ["a", "b"], [1], id="earlier_chunk_fully_deduplicated"),
        ],
    )
    def test_prepends_unique(self, values, expected, contributors):
        result = FieldPrependUnique()(values)

        assert result == FieldMergeResult(value=expected, contributors=contributors)


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
