"""Tests for loading/context.py."""

from dataclasses import dataclass, fields
from enum import Flag
from pathlib import Path
from typing import Any

import pytest

from dature.field_path import FieldPath
from dature.loading.context import (
    apply_skip_invalid,
    build_error_ctx,
    coerce_flag_fields,
    get_allowed_fields,
    merge_fields,
)
from dature.loading.retort import RetortCache
from dature.sources.base import IndexedSource
from dature.sources.env_ import EnvSource
from dature.sources.json_ import JsonSource


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


class Permission(Flag):
    READ = 1
    WRITE = 2
    EXECUTE = 4


@dataclass
class FlagConfig:
    name: str
    perms: Permission


_PERMS: frozenset[str] = frozenset({"perms"})


class TestCoerceFlagFields:
    @pytest.mark.parametrize(
        ("flag_field_names", "data", "expected"),
        [
            pytest.param(_PERMS, {"name": "test", "perms": "3"}, {"name": "test", "perms": 3}, id="string-to-int"),
            pytest.param(_PERMS, {"name": "test", "perms": 3}, {"name": "test", "perms": 3}, id="int-unchanged"),
            pytest.param(
                _PERMS,
                {"name": "test", "perms": Permission.READ | Permission.WRITE},
                {"name": "test", "perms": 3},
                id="flag-object-to-int",
            ),
            pytest.param(
                _PERMS,
                {"name": "test", "perms": "READ|WRITE"},
                {"name": "test", "perms": "READ|WRITE"},
                id="non-numeric-string-unchanged",
            ),
            pytest.param(_PERMS, {"name": "test"}, {"name": "test"}, id="missing-flag-field"),
            pytest.param(
                _PERMS,
                {"name": "hello", "perms": "5"},
                {"name": "hello", "perms": 5},
                id="non-flag-field-untouched",
            ),
            pytest.param(
                frozenset(),
                {"name": "test", "perms": "3"},
                {"name": "test", "perms": "3"},
                id="empty-set-returns-data-as-is",
            ),
            pytest.param(_PERMS, [1, 2, 3], [1, 2, 3], id="non-dict-returned-as-is"),
        ],
    )
    def test_coerce(self, flag_field_names: frozenset[str], data: Any, expected: Any):
        assert coerce_flag_fields(data, flag_field_names) == expected

    def test_retort_cache_derives_flag_field_names(self):
        assert RetortCache(FlagConfig).flag_field_names == _PERMS


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
    @pytest.mark.parametrize("skip_field_if_invalid", [False, None], ids=["false", "none"])
    def test_falsy_returns_raw_unchanged(self, tmp_path: Path, skip_field_if_invalid):
        json_file = tmp_path / "config.json"
        json_file.write_text("{}")

        @dataclass
        class Cfg:
            name: str

        raw = {"name": "hello"}

        result = apply_skip_invalid(
            raw=raw,
            skip_field_if_invalid=skip_field_if_invalid,
            schema=Cfg,
            log_prefix="[test]",
        )

        assert result.cleaned_dict == raw
        assert result.skipped_paths == []


class TestRetortCache:
    def test_plain_creates_and_caches_retort(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text("{}")

        @dataclass
        class Cfg:
            name: str

        source = JsonSource(file=json_file)
        cache = RetortCache(Cfg, cache_engine=True)

        first = cache.plain(IndexedSource(source, 0))
        second = cache.plain(IndexedSource(source, 0))

        assert first is second
