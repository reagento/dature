"""Tests for main.py — public load() API."""

from dataclasses import dataclass, field
from pathlib import Path

import pytest

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


class TestCache:
    def test_cache_enabled_by_default(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')

        metadata = JsonSource(file=json_file)

        @load(metadata)
        @dataclass
        class Config:
            name: str
            port: int

        first = Config()
        json_file.write_text('{"name": "updated", "port": 9090}')
        second = Config()

        assert first.name == "original"
        assert second.name == "original"

    def test_cache_disabled(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')

        metadata = JsonSource(file=json_file)

        @load(metadata, cache=False)
        @dataclass
        class Config:
            name: str
            port: int

        first = Config()
        json_file.write_text('{"name": "updated", "port": 9090}')
        second = Config()

        assert first.name == "original"
        assert second.name == "updated"


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
