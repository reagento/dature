"""Tests for deep merge algorithms and conflict detection."""

import pytest

from dature.merging.deep_merge import deep_merge_first_wins, deep_merge_last_wins

_DISPATCH = {
    "last_wins": deep_merge_last_wins,
    "first_wins": deep_merge_first_wins,
}


class TestDeepMerge:
    @pytest.mark.parametrize(
        ("base", "override", "strategy", "expected"),
        [
            pytest.param(
                {"a": 1, "b": 2},
                {"b": 3, "c": 4},
                "last_wins",
                {"a": 1, "b": 3, "c": 4},
                id="flat_last_wins",
            ),
            pytest.param(
                {"a": 1, "b": 2},
                {"b": 3, "c": 4},
                "first_wins",
                {"a": 1, "b": 2, "c": 4},
                id="flat_first_wins",
            ),
            pytest.param(
                {"db": {"host": "localhost", "port": 5432}},
                {"db": {"host": "prod-host", "name": "mydb"}},
                "last_wins",
                {"db": {"host": "prod-host", "port": 5432, "name": "mydb"}},
                id="nested_last_wins",
            ),
            pytest.param(
                {"db": {"host": "localhost", "port": 5432}},
                {"db": {"host": "prod-host", "name": "mydb"}},
                "first_wins",
                {"db": {"host": "localhost", "port": 5432, "name": "mydb"}},
                id="nested_first_wins",
            ),
            pytest.param(
                {"a": {"b": {"c": 1, "d": 2}}},
                {"a": {"b": {"c": 99, "e": 3}}},
                "last_wins",
                {"a": {"b": {"c": 99, "d": 2, "e": 3}}},
                id="deeply_nested",
            ),
            pytest.param(
                {"tags": ["a", "b"]},
                {"tags": ["c"]},
                "last_wins",
                {"tags": ["c"]},
                id="lists_replaced_entirely",
            ),
            pytest.param(
                {},
                {"a": 1},
                "last_wins",
                {"a": 1},
                id="empty_base",
            ),
            pytest.param(
                {"a": 1},
                {},
                "last_wins",
                {"a": 1},
                id="empty_override",
            ),
            pytest.param(
                {},
                {},
                "last_wins",
                {},
                id="both_empty",
            ),
            pytest.param(
                "old",
                "new",
                "last_wins",
                "new",
                id="scalar_last_wins",
            ),
            pytest.param(
                "old",
                "new",
                "first_wins",
                "old",
                id="scalar_first_wins",
            ),
            pytest.param(
                {"a": None},
                {"a": 1},
                "last_wins",
                {"a": 1},
                id="none_value_last_wins",
            ),
            pytest.param(
                {"a": None},
                {"a": 1},
                "first_wins",
                {"a": None},
                id="none_value_first_wins",
            ),
            pytest.param(
                {"a": {"nested": 1}},
                {"a": "scalar"},
                "last_wins",
                {"a": "scalar"},
                id="dict_vs_scalar_last_wins",
            ),
            pytest.param(
                {"a": "scalar"},
                {"a": {"nested": 1}},
                "last_wins",
                {"a": {"nested": 1}},
                id="scalar_vs_dict_last_wins",
            ),
            pytest.param(
                {"a": {"nested": 1}},
                {"a": "scalar"},
                "first_wins",
                {"a": {"nested": 1}},
                id="dict_vs_scalar_first_wins",
            ),
        ],
    )
    def test_merge(self, base, override, strategy, expected):
        assert _DISPATCH[strategy](base, override) == expected


class TestDeepMergeLastWins:
    @pytest.mark.parametrize(
        ("base", "override", "expected"),
        [
            pytest.param("old", "new", "new", id="strings"),
            pytest.param(1, 2, 2, id="ints"),
            pytest.param([1], [2], [2], id="lists"),
            pytest.param({"a": 1}, "scalar", "scalar", id="dict_vs_scalar"),
            pytest.param("scalar", {"a": 1}, {"a": 1}, id="scalar_vs_dict"),
        ],
    )
    def test_non_dict_returns_override(self, base, override, expected):
        assert deep_merge_last_wins(base, override) == expected


class TestDeepMergeFirstWins:
    @pytest.mark.parametrize(
        ("base", "override", "expected"),
        [
            pytest.param("old", "new", "old", id="strings"),
            pytest.param(1, 2, 1, id="ints"),
            pytest.param([1], [2], [1], id="lists"),
            pytest.param({"a": 1}, "scalar", {"a": 1}, id="dict_vs_scalar"),
            pytest.param("scalar", {"a": 1}, "scalar", id="scalar_vs_dict"),
        ],
    )
    def test_non_dict_returns_base(self, base, override, expected):
        assert deep_merge_first_wins(base, override) == expected
