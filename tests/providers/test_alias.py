"""Tests for providers/alias.py."""

from dataclasses import dataclass

import pytest

from dature import EnvSource, load
from dature.field_path import F, FieldPath
from dature.providers.alias import AliasEntry, CrossLevelEntry, build_alias_map, transform_dict


@dataclass
class _Named:
    name: str


@dataclass
class _Address:
    city: str


@dataclass
class _User:
    address: _Address


@dataclass
class _NameAge:
    name: str
    age: int


class TestBuildAliasMap:
    def test_flat_type_owner(self):
        mapping = {F[_Named].name: "fullName"}

        result = build_alias_map(mapping)

        assert result == {_Named: [AliasEntry(field_name="name", aliases=("fullName",))]}

    def test_flat_string_owner(self):
        mapping = {F["Config"].name: "fullName"}

        result = build_alias_map(mapping)

        assert result == {"Config": [AliasEntry(field_name="name", aliases=("fullName",))]}

    def test_tuple_aliases(self):
        mapping = {F[_Named].name: ("fullName", "userName")}

        result = build_alias_map(mapping)

        assert result == {_Named: [AliasEntry(field_name="name", aliases=("fullName", "userName"))]}

    def test_nested_path_resolves_to_leaf_owner(self):
        mapping = {F[_User].address.city: "cityName"}

        result = build_alias_map(mapping)

        assert result == {
            _Address: [AliasEntry(field_name="city", aliases=("cityName",))],
            _User: [CrossLevelEntry(dest_path=("address",), field_name="city", aliases=("cityName",))],
        }

    def test_nested_string_owner_raises(self):
        mapping = {FieldPath(owner="User", parts=("address", "city")): "cityName"}

        with pytest.raises(TypeError) as exc_info:
            build_alias_map(mapping)

        assert str(exc_info.value) == (
            "Nested FieldPath with string owner 'User' is not supported — cannot resolve intermediate types"
        )

    def test_empty_field_path_raises(self):
        mapping = {FieldPath(owner="Config"): "fullName"}

        with pytest.raises(ValueError, match="FieldPath must contain at least one field name"):
            build_alias_map(mapping)

    def test_multiple_fields_same_owner(self):
        mapping = {
            F[_NameAge].name: "fullName",
            F[_NameAge].age: "userAge",
        }

        result = build_alias_map(mapping)

        assert sorted(result[_NameAge], key=lambda e: e.field_name) == [
            AliasEntry(field_name="age", aliases=("userAge",)),
            AliasEntry(field_name="name", aliases=("fullName",)),
        ]


class TestTransformDict:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({"fullName": "Alice"}, {"name": "Alice"}),
            ({"fullName": "Alice", "userName": "Bob"}, {"name": "Alice", "userName": "Bob"}),
            ({"name": "Direct", "fullName": "Alias"}, {"name": "Direct", "fullName": "Alias"}),
            ({"other": "value"}, {"other": "value"}),
            ({"userName": "Bob"}, {"name": "Bob"}),
        ],
        ids=["canonical", "first_alias_wins", "canonical_not_overwritten", "no_match", "second_alias"],
    )
    def test_dict_input(self, data: dict[str, str], expected: dict[str, str]):
        entries = [AliasEntry(field_name="name", aliases=("fullName", "userName"))]

        result = transform_dict(data, entries)

        assert result == expected

    @pytest.mark.parametrize(
        "input_value",
        ["string", 42, None],
        ids=["string", "int", "none"],
    )
    def test_non_dict_returns_as_is(self, input_value: object):
        entries = [AliasEntry(field_name="name", aliases=("fullName",))]

        assert transform_dict(input_value, entries) == input_value


class TestAliasProviderIntegration:
    def test_alias_applied_via_load(self, monkeypatch):
        monkeypatch.setenv("APP_FULL_NAME", "Alice")

        result = load(
            EnvSource(prefix="APP_", field_mapping={F[_Named].name: "full_name"}),
            schema=_Named,
        )

        assert result == _Named(name="Alice")

    def test_nested_field_path_with_intermediate_non_dataclass_raises(self):
        mapping = {FieldPath(owner=_Named, parts=("name", "sub")): "alias"}

        with pytest.raises(TypeError) as exc_info:
            build_alias_map(mapping)

        assert str(exc_info.value) == "Intermediate field 'name' of type '<class 'str'>' is not a dataclass"
