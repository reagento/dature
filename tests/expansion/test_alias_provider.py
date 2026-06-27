from dataclasses import dataclass

import pytest

from dature import EnvSource, load
from dature.expansion.alias_provider import AliasEntry, _build_alias_map, _transform_dict
from dature.field_path import F, FieldPath


class TestBuildAliasMap:
    def test_flat_type_owner(self):
        @dataclass
        class Config:
            name: str

        mapping = {F[Config].name: "fullName"}
        result = _build_alias_map(mapping)

        assert Config in result
        assert len(result[Config]) == 1
        assert result[Config][0] == AliasEntry(field_name="name", aliases=("fullName",))

    def test_flat_string_owner(self):
        mapping = {F["Config"].name: "fullName"}
        result = _build_alias_map(mapping)

        assert "Config" in result
        assert result["Config"][0] == AliasEntry(field_name="name", aliases=("fullName",))

    def test_tuple_aliases(self):
        @dataclass
        class Config:
            name: str

        mapping = {F[Config].name: ("fullName", "userName")}
        result = _build_alias_map(mapping)

        assert result[Config][0] == AliasEntry(
            field_name="name",
            aliases=("fullName", "userName"),
        )

    def test_nested_path_resolves_to_leaf_owner(self):
        @dataclass
        class Address:
            city: str

        @dataclass
        class User:
            address: Address

        mapping = {F[User].address.city: "cityName"}
        result = _build_alias_map(mapping)

        assert Address in result
        assert result[Address][0] == AliasEntry(field_name="city", aliases=("cityName",))

    def test_nested_string_owner_raises(self):
        mapping = {FieldPath(owner="User", parts=("address", "city")): "cityName"}

        with pytest.raises(TypeError) as exc_info:
            _build_alias_map(mapping)

        assert str(exc_info.value) == (
            "Nested FieldPath with string owner 'User' is not supported — cannot resolve intermediate types"
        )

    def test_empty_field_path_raises(self):
        mapping = {FieldPath(owner="Config"): "fullName"}

        with pytest.raises(ValueError, match="FieldPath must contain at least one field name") as exc_info:
            _build_alias_map(mapping)

        assert str(exc_info.value) == "FieldPath must contain at least one field name"

    def test_multiple_fields_same_owner(self):
        @dataclass
        class Config:
            name: str
            age: int

        mapping = {
            F[Config].name: "fullName",
            F[Config].age: "userAge",
        }
        result = _build_alias_map(mapping)

        assert len(result[Config]) == 2
        field_names = {e.field_name for e in result[Config]}
        assert field_names == {"name", "age"}


class TestTransformDict:
    def test_replaces_alias_with_canonical(self):
        entries = [AliasEntry(field_name="name", aliases=("fullName",))]
        data = {"fullName": "Alice"}

        result = _transform_dict(data, entries)

        assert result == {"name": "Alice"}

    def test_first_alias_wins(self):
        entries = [AliasEntry(field_name="name", aliases=("fullName", "userName"))]
        data = {"fullName": "Alice", "userName": "Bob"}

        result = _transform_dict(data, entries)

        assert result == {"name": "Alice", "userName": "Bob"}

    def test_canonical_name_not_overwritten(self):
        entries = [AliasEntry(field_name="name", aliases=("fullName",))]
        data = {"name": "Direct", "fullName": "Alias"}

        result = _transform_dict(data, entries)

        assert result == {"name": "Direct", "fullName": "Alias"}

    def test_no_matching_alias(self):
        entries = [AliasEntry(field_name="name", aliases=("fullName",))]
        data = {"other": "value"}

        result = _transform_dict(data, entries)

        assert result == {"other": "value"}

    @pytest.mark.parametrize(
        ("input_value", "expected"),
        [
            ("string", "string"),
            (42, 42),
            (None, None),
        ],
    )
    def test_non_dict_returns_as_is(self, input_value, expected):
        entries = [AliasEntry(field_name="name", aliases=("fullName",))]

        assert _transform_dict(input_value, entries) == expected

    def test_fallback_to_second_alias(self):
        entries = [AliasEntry(field_name="name", aliases=("fullName", "userName"))]
        data = {"userName": "Bob"}

        result = _transform_dict(data, entries)

        assert result == {"name": "Bob"}


class TestAliasProviderIntegration:
    def test_alias_applied_via_load(self, monkeypatch):
        @dataclass
        class Config:
            name: str

        monkeypatch.setenv("APP_FULL_NAME", "Alice")

        result = load(
            EnvSource(prefix="APP_", field_mapping={F[Config].name: "full_name"}),
            schema=Config,
        )

        assert result == Config(name="Alice")

    def test_nested_field_path_with_intermediate_non_dataclass_raises(self):
        @dataclass
        class Config:
            name: str

        mapping = {FieldPath(owner=Config, parts=("name", "sub")): "alias"}

        with pytest.raises(TypeError) as exc_info:
            _build_alias_map(mapping)

        assert str(exc_info.value) == "Intermediate field 'name' of type '<class 'str'>' is not a dataclass"
