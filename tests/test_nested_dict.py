"""Unit tests for dature.nested_dict — pure dotted-path dict helpers."""

import pytest

from dature.nested_dict import (
    ABSENT,
    collect_field_values,
    collect_leaf_paths,
    collect_not_loaded_paths,
    flatten_dict,
    get_nested_value,
    remove_path_from_dict,
    set_nested_value,
)
from dature.type_aliases import NOT_LOADED


class TestCollectLeafPaths:
    @pytest.mark.parametrize(
        ("data", "prefix", "expected"),
        [
            ({"a": 1}, "", ["a"]),
            ({"a": {"b": 2}}, "", ["a.b"]),
            ({"a": {"b": {"c": 3}}}, "", ["a.b.c"]),
            ({"a": 1, "b": 2}, "", ["a", "b"]),
            ({"a": {"b": 1}, "c": 2}, "", ["a.b", "c"]),
            ({"a": [1, 2]}, "", ["a"]),  # list is a leaf, not recursed
            ({"a": None}, "", ["a"]),  # None is a leaf
            ([1, 2], "", []),  # non-dict root
            ("string", "", []),
            (42, "", []),
            (None, "", []),
            ({}, "", []),
            ({"x": 1}, "parent", ["parent.x"]),
            ({"x": {"y": 1}}, "parent", ["parent.x.y"]),
        ],
    )
    def test_cases(self, data, prefix, expected):
        assert collect_leaf_paths(data, prefix) == expected


class TestFlattenDict:
    @pytest.mark.parametrize(
        ("data", "prefix", "expected"),
        [
            ({"a": 1}, "", [("a", 1)]),
            ({"a": {"b": 2}}, "", [("a.b", 2)]),
            ({"a": 1, "b": 2}, "", [("a", 1), ("b", 2)]),
            ([1, 2], "", []),  # non-dict inputs → empty
            ("string", "", []),
            (42, "", []),
            (None, "", []),
            ({}, "", []),
            ({"a": [1, 2]}, "", [("a", [1, 2])]),  # list is a leaf
            ({"x": 1}, "root", [("root.x", 1)]),
            ({"x": {"y": 2}}, "root", [("root.x.y", 2)]),
        ],
    )
    def test_cases(self, data, prefix, expected):
        assert flatten_dict(data, prefix=prefix) == expected


class TestGetNestedValue:
    @pytest.mark.parametrize(
        ("data", "path", "expected"),
        [
            ({"a": 1}, "a", 1),
            ({"a": {"b": 2}}, "a.b", 2),
            ({"a": {"b": {"c": 3}}}, "a.b.c", 3),
        ],
    )
    def test_returns_value(self, data, path, expected):
        assert get_nested_value(data, path) == expected

    def test_stored_none_returns_none_not_absent(self):
        # None stored under a key must come back as None, not the ABSENT sentinel.
        result = get_nested_value({"a": None}, "a")

        assert result is None

    @pytest.mark.parametrize(
        ("data", "path"),
        [
            ({"a": 1}, "b"),  # missing key
            ({"a": {}}, "a.b"),  # missing key in nested dict
            ({"a": 42}, "a.b"),  # non-dict intermediate
            ([1, 2], "a"),  # non-dict root
            (None, "a"),
            ("string", "a"),
            ({}, "a"),
        ],
    )
    def test_returns_absent(self, data, path):
        assert get_nested_value(data, path) is ABSENT


class TestCollectFieldValues:
    @pytest.mark.parametrize(
        ("raw_dicts", "path", "expected"),
        [
            ([{"a": 1}, {"a": 2}, {"a": 3}], "a", [1, 2, 3]),
            ([{"a": 1}, {"b": 2}, {"a": 3}], "a", [1, 3]),  # missing key skipped
            ([{"x": {"y": 10}}, {"x": {"y": 20}}], "x.y", [10, 20]),
            ([], "a", []),
            ([{"a": None}, {"a": 1}], "a", [None, 1]),  # None is a valid value
        ],
    )
    def test_cases(self, raw_dicts, path, expected):
        assert collect_field_values(raw_dicts, path) == expected


class TestSetNestedValue:
    @pytest.mark.parametrize(
        ("data", "path", "value", "expected"),
        [
            ({"a": 1, "b": 2}, "a", 99, {"a": 99, "b": 2}),
            ({"x": {"y": 1}}, "x.y", 42, {"x": {"y": 42}}),
            ({"a": 1}, "b", 2, {"a": 1, "b": 2}),  # add new key
            # "a" is 1 (not a dict), so nested path can't be followed → unchanged
            ({"a": 1}, "a.b", 99, {"a": 1}),
            ([1, 2], "a", 99, [1, 2]),  # non-dict input returned as-is
            (None, "a", 99, None),
            (42, "a", 99, 42),
        ],
    )
    def test_cases(self, data, path, value, expected):
        assert set_nested_value(data, path, value) == expected

    def test_original_dict_is_not_mutated(self):
        original = {"a": 1}
        set_nested_value(original, "a", 99)

        assert original == {"a": 1}


class TestCollectNotLoadedPaths:
    @pytest.mark.parametrize(
        ("data", "prefix", "expected"),
        [
            ({"a": NOT_LOADED, "b": 1}, "", ["a"]),
            ({"x": {"y": NOT_LOADED, "z": 2}}, "", ["x.y"]),
            ({"a": 1, "b": "ok"}, "", []),
            ({"a": NOT_LOADED, "b": {"c": NOT_LOADED}}, "", ["a", "b.c"]),
            ({"key": NOT_LOADED}, "parent", ["parent.key"]),
        ],
    )
    def test_cases(self, data, prefix, expected):
        assert collect_not_loaded_paths(data, prefix) == expected


class TestRemovePathFromDict:
    @pytest.mark.parametrize(
        ("initial", "path", "expected_after"),
        [
            ({"a": 1, "b": 2}, "a", {"b": 2}),
            ({"x": {"y": 1, "z": 2}}, "x.y", {"x": {"z": 2}}),
            ({"a": 1}, "b", {"a": 1}),  # missing key — no-op
            ({"a": {"b": 1}}, "a.c", {"a": {"b": 1}}),  # missing nested key — no-op
            ({"a": 42}, "a.b", {"a": 42}),  # non-dict intermediate — no-op
        ],
    )
    def test_cases(self, initial, path, expected_after):
        remove_path_from_dict(initial, path)

        assert initial == expected_after

    def test_modifies_in_place(self):
        data = {"a": 1, "b": 2}
        original_id = id(data)
        remove_path_from_dict(data, "a")

        assert id(data) == original_id
