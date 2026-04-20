"""Tests for loading/context.py."""

from dataclasses import dataclass, fields
from enum import Flag
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from dature.field_path import FieldPath
from dature.loading.context import (
    apply_skip_invalid,
    build_error_ctx,
    coerce_flag_fields,
    get_allowed_fields,
    make_validating_post_init,
    merge_fields,
)
from dature.sources.env_ import EnvSource
from dature.sources.json_ import JsonSource
from dature.sources.retort import _retort_cache_key, ensure_retort


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


class TestBuildErrorCtx:
    def test_file_source(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text("{}")
        source = JsonSource(file=json_file, prefix="app")

        ctx = build_error_ctx(source, "MyConfig")

        assert ctx.dataclass_name == "MyConfig"
        assert ctx.source is source

    def test_flat_key_source(self):
        source = EnvSource(prefix="APP", nested_sep="__")

        ctx = build_error_ctx(source, "MyConfig")

        assert ctx.source is source


class TestGetAllowedFields:
    def test_bool_returns_none(self):
        assert get_allowed_fields(skip_value=True) is None
        assert get_allowed_fields(skip_value=False) is None

    def test_tuple_of_field_paths(self):
        @dataclass
        class Cfg:
            name: str
            port: int

        fp = FieldPath(owner=Cfg, parts=("name",))

        result = get_allowed_fields(skip_value=(fp,), schema=Cfg)

        assert result == {"name"}


class TestApplySkipInvalid:
    @pytest.mark.parametrize("skip_if_invalid", [False, None], ids=["false", "none"])
    def test_falsy_returns_raw_unchanged(self, tmp_path: Path, skip_if_invalid):
        json_file = tmp_path / "config.json"
        json_file.write_text("{}")

        @dataclass
        class Cfg:
            name: str

        source = JsonSource(file=json_file)
        raw = {"name": "hello"}

        result = apply_skip_invalid(
            raw=raw,
            skip_if_invalid=skip_if_invalid,
            source=source,
            schema=Cfg,
            log_prefix="[test]",
        )

        assert result.cleaned_dict == raw
        assert result.skipped_paths == []


class TestEnsureRetort:
    def test_creates_and_caches_retort(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text("{}")

        @dataclass
        class Cfg:
            name: str

        source = JsonSource(file=json_file)
        key = _retort_cache_key(Cfg, None)
        assert key not in source.retorts

        ensure_retort(source, Cfg)
        assert key in source.retorts

        first = source.retorts[key]
        ensure_retort(source, Cfg)
        assert source.retorts[key] is first


class TestMakeValidatingPostInit:
    @dataclass
    class Cfg:
        name: str

    def test_loading_flag_skips_validation(self):
        ctx = MagicMock()
        ctx.loading = True
        ctx.validating = False
        ctx.original_post_init = None

        post_init = make_validating_post_init(ctx)
        instance = MagicMock()
        post_init(instance)

        ctx.validation_loader.assert_not_called()

    def test_validating_flag_skips_reentrant(self):
        ctx = MagicMock()
        ctx.loading = False
        ctx.validating = True
        ctx.original_post_init = None

        post_init = make_validating_post_init(ctx)
        instance = MagicMock()
        post_init(instance)

        ctx.validation_loader.assert_not_called()

    def test_calls_original_post_init(self):
        original = MagicMock()
        ctx = MagicMock()
        ctx.loading = False
        ctx.validating = False
        ctx.original_post_init = original
        ctx.cls = self.Cfg
        ctx.validation_loader = MagicMock()
        ctx.error_ctx = MagicMock()

        post_init = make_validating_post_init(ctx)
        instance = self.Cfg(name="test")
        post_init(instance)

        original.assert_called_once_with(instance)
