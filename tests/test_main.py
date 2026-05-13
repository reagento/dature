"""Tests for main.py — public load() API."""

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import pytest
import time_machine

from dature import (
    EnvFileSource,
    EnvSource,
    IniSource,
    Json5Source,
    JsonSource,
    Source,
    Toml10Source,
    Toml11Source,
    Yaml11Source,
    Yaml12Source,
    load,
)


def _all_file_sources() -> list[type[Source]]:
    return [EnvFileSource, Yaml11Source, Yaml12Source, JsonSource, Json5Source, Toml10Source, Toml11Source, IniSource]


class TestLoadAsDecorator:
    def test_loads_from_file(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "FromFile", "port": 8080}')

        metadata = JsonSource(file=json_file)

        @load(metadata)
        @dataclass
        class Config:
            name: str
            port: int

        config = Config()
        assert config.name == "FromFile"
        assert config.port == 8080

    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_NAME", "EnvApp")
        monkeypatch.setenv("APP_PORT", "3000")

        metadata = EnvSource(prefix="APP_")

        @load(metadata)
        @dataclass
        class Config:
            name: str
            port: int

        config = Config()
        assert config.name == "EnvApp"
        assert config.port == 3000

    def test_default_metadata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_VAR", "test_value")

        @load(EnvSource())
        @dataclass
        class Config:
            my_var: str

        config = Config()
        assert config.my_var == "test_value"

    def test_explicit_loader_overrides_extension(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "config.txt"
        txt_file.write_text('{"app_name": "OverrideApp"}')

        metadata = JsonSource(file=txt_file)

        @load(metadata)
        @dataclass
        class Config:
            app_name: str

        config = Config()
        assert config.app_name == "OverrideApp"

    def test_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOADED_VAR", "loaded")
        monkeypatch.setenv("OVERRIDDEN_VAR", "loaded")

        @load(EnvSource())
        @dataclass
        class Config:
            overridden_var: str
            default_var: str = field(default="default")
            loaded_var: str = field(default="default")

        config = Config(overridden_var="from_init")

        assert config.default_var == "default"
        assert config.loaded_var == "loaded"
        assert config.overridden_var == "from_init"

    def test_invalid_decorator_order(self) -> None:
        with pytest.raises(TypeError, match="Config must be a dataclass"):

            @dataclass
            @load(EnvSource())
            class Config:
                pass


_SENTINEL: object = object()


class TestCache:
    @pytest.mark.parametrize(
        ("cache_arg", "advance_seconds", "expected_second"),
        [
            (_SENTINEL, 0.0, "original"),
            (True, 0.0, "original"),
            (False, 0.0, "updated"),
            (timedelta(seconds=30), 10.0, "original"),
            (timedelta(seconds=30), 31.0, "updated"),
            (timedelta(0), 0.0, "updated"),
        ],
        ids=["default", "true", "false", "ttl-hit", "ttl-expired", "ttl-zero"],
    )
    def test_decorator_cache_matrix(
        self,
        tmp_path: Path,
        time_control: time_machine.Traveller,
        cache_arg: object,
        advance_seconds: float,
        expected_second: str,
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')
        metadata = JsonSource(file=json_file)

        if cache_arg is _SENTINEL:
            decorator = load(metadata)
        else:
            decorator = load(metadata, cache=cache_arg)

        @decorator
        @dataclass
        class Config:
            name: str
            port: int

        first = Config()
        json_file.write_text('{"name": "updated", "port": 9090}')
        time_control.shift(advance_seconds)
        second = Config()

        assert first.name == "original"
        assert second.name == expected_second

    def test_negative_timedelta_raises(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "x", "port": 1}')

        @dataclass
        class Config:
            name: str
            port: int

        with pytest.raises(ValueError, match="cache timedelta must be non-negative"):
            load(JsonSource(file=json_file), cache=timedelta(seconds=-1))


class TestLoadAsFunctionCache:
    @pytest.mark.parametrize(
        ("cache_arg", "advance_seconds", "expected_second"),
        [
            (True, 0.0, "original"),
            (False, 0.0, "updated"),
            (timedelta(seconds=30), 10.0, "original"),
            (timedelta(seconds=30), 31.0, "updated"),
            (timedelta(0), 0.0, "updated"),
        ],
        ids=["true", "false", "ttl-hit", "ttl-expired", "ttl-zero"],
    )
    def test_function_cache_matrix(
        self,
        tmp_path: Path,
        time_control: time_machine.Traveller,
        cache_arg: object,
        advance_seconds: float,
        expected_second: str,
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')
        source = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        first = load(source, schema=Config, cache=cache_arg)
        json_file.write_text('{"name": "updated", "port": 9090}')
        time_control.shift(advance_seconds)
        second = load(source, schema=Config, cache=cache_arg)

        assert first.name == "original"
        assert second.name == expected_second

    def test_function_cache_per_schema(self, tmp_path: Path) -> None:
        a_file = tmp_path / "a.json"
        a_file.write_text('{"name": "A"}')
        source = JsonSource(file=a_file)

        @dataclass
        class ConfigA:
            name: str

        @dataclass
        class ConfigB:
            name: str

        first_a = load(source, schema=ConfigA, cache=True)
        first_b = load(source, schema=ConfigB, cache=True)

        assert first_a.name == "A"
        assert first_b.name == "A"
        assert type(first_a).__name__ == "ConfigA"
        assert type(first_b).__name__ == "ConfigB"

    def test_function_cache_different_sources_independent(self, tmp_path: Path) -> None:
        a_file = tmp_path / "a.json"
        a_file.write_text('{"name": "A"}')
        b_file = tmp_path / "b.json"
        b_file.write_text('{"name": "B"}')

        source_a = JsonSource(file=a_file)
        source_b = JsonSource(file=b_file)

        @dataclass
        class Config:
            name: str

        cfg_a = load(source_a, schema=Config, cache=True)
        cfg_b = load(source_b, schema=Config, cache=True)

        assert cfg_a.name == "A"
        assert cfg_b.name == "B"


class TestLoadAsFunction:
    def test_loads_from_file(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "FromFile", "port": 9090}')

        @dataclass
        class Config:
            name: str
            port: int

        metadata = JsonSource(file=json_file)
        result = load(metadata, schema=Config)

        assert result.name == "FromFile"
        assert result.port == 9090

    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_NAME", "EnvFunc")
        monkeypatch.setenv("APP_DEBUG", "true")

        @dataclass
        class Config:
            name: str
            debug: bool

        metadata = EnvSource(prefix="APP_")
        result = load(metadata, schema=Config)

        assert result.name == "EnvFunc"
        assert result.debug is True

    def test_default_metadata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_VAR", "from_env")

        @dataclass
        class Config:
            my_var: str

        result = load(EnvSource(), schema=Config)

        assert result.my_var == "from_env"


class TestFileNotFoundWithLoad:
    @pytest.mark.parametrize(
        "source_class",
        _all_file_sources(),
    )
    def test_load_function_single_source_filenot_found(self, source_class: type[Source]) -> None:

        @dataclass
        class Config:
            name: str

        metadata = source_class(file="/non/existent/file.json")

        with pytest.raises(FileNotFoundError):
            load(metadata, schema=Config)

    @pytest.mark.parametrize(
        "source_class",
        _all_file_sources(),
    )
    def test_load_decorator_single_source_filenot_found(self, source_class: type[Source]) -> None:
        metadata = source_class(file="/non/existent/config.json")

        @load(metadata)
        @dataclass
        class Config:
            name: str

        with pytest.raises(FileNotFoundError):
            Config()
