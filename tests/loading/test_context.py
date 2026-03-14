"""Tests for loading/context.py."""

from dataclasses import dataclass, fields
from enum import Flag
from typing import Any

from dature.loading.context import coerce_flag_fields, merge_fields


class TestMergeFields:
    @dataclass
    class Config:
        name: str
        port: int
        debug: bool

    @dataclass
    class Loaded:
        name: str = "loaded_name"
        port: int = 8080
        debug: bool = True

    def _field_list(self) -> tuple[Any, ...]:
        return fields(self.Config)

    def test_no_explicit_fields(self):
        loaded = self.Loaded()

        result = merge_fields(loaded, self._field_list(), (), {})

        assert result == {"name": "loaded_name", "port": 8080, "debug": True}

    def test_all_kwargs_explicit(self):
        loaded = self.Loaded()
        kwargs = {"name": "explicit", "port": 9090, "debug": False}

        result = merge_fields(loaded, self._field_list(), (), kwargs)

        assert result == {"name": "explicit", "port": 9090, "debug": False}

    def test_partial_kwargs(self):
        loaded = self.Loaded()

        result = merge_fields(loaded, self._field_list(), (), {"name": "explicit"})

        assert result == {"name": "explicit", "port": 8080, "debug": True}

    def test_positional_args(self):
        loaded = self.Loaded()

        result = merge_fields(loaded, self._field_list(), ("positional_name",), {})

        assert result == {"port": 8080, "debug": True}

    def test_mixed_args_and_kwargs(self):
        loaded = self.Loaded()

        result = merge_fields(
            loaded,
            self._field_list(),
            ("positional_name",),
            {"debug": False},
        )

        assert result == {"port": 8080, "debug": False}

    def test_args_beyond_field_count_ignored(self):
        loaded = self.Loaded()

        result = merge_fields(
            loaded,
            self._field_list(),
            ("a", "b", "c", "extra"),
            {},
        )

        assert result == {}


class TestCoerceFlagFields:
    class Permission(Flag):
        READ = 1
        WRITE = 2
        EXECUTE = 4

    @dataclass
    class FlagConfig:
        name: str
        perms: "TestCoerceFlagFields.Permission"

    def test_string_value_coerced_to_int(self):
        data = {"name": "test", "perms": "3"}

        result = coerce_flag_fields(data, self.FlagConfig)

        assert result == {"name": "test", "perms": 3}

    def test_int_value_unchanged(self):
        data = {"name": "test", "perms": 3}

        result = coerce_flag_fields(data, self.FlagConfig)

        assert result == {"name": "test", "perms": 3}

    def test_non_flag_string_fields_unchanged(self):
        data = {"name": "hello", "perms": "5"}

        result = coerce_flag_fields(data, self.FlagConfig)

        assert result["name"] == "hello"

    def test_non_dict_data_returned_as_is(self):
        result = coerce_flag_fields([1, 2, 3], self.FlagConfig)

        assert result == [1, 2, 3]

    def test_non_dataclass_returns_data_as_is(self):
        data = {"name": "test", "perms": "3"}

        result = coerce_flag_fields(data, str)

        assert result == {"name": "test", "perms": "3"}

    def test_missing_flag_field_no_error(self):
        data = {"name": "test"}

        result = coerce_flag_fields(data, self.FlagConfig)

        assert result == {"name": "test"}

    def test_non_numeric_string_left_unchanged(self):
        data = {"name": "test", "perms": "READ|WRITE"}

        result = coerce_flag_fields(data, self.FlagConfig)

        assert result == {"name": "test", "perms": "READ|WRITE"}

    def test_flag_object_coerced_to_int(self):
        data = {"name": "test", "perms": self.Permission.READ | self.Permission.WRITE}

        result = coerce_flag_fields(data, self.FlagConfig)

        assert result == {"name": "test", "perms": 3}
