"""Tests for main.py — public load() API."""

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import ClassVar

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
    VaultSource,
    Yaml11Source,
    Yaml12Source,
    configure,
    load,
)
from dature.types import JSONValue


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
    def test_function_load_does_not_cache_across_calls(self, tmp_path: Path) -> None:
        """A throwaway ``load(...)`` does not retain cache between calls."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')
        source = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        first = load(source, schema=Config, cache=True)
        json_file.write_text('{"name": "updated", "port": 9090}')
        second = load(source, schema=Config, cache=True)

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


@dataclass(kw_only=True, repr=False)
class _ConfigAwareSource(Source):
    """Single-field source that emits its own ``url`` so we can assert config-merge happened."""

    url: str | None = None
    format_name = "_config_aware"
    location_label: ClassVar[str] = "TEST"
    config_group: ClassVar[str | None] = "vault"

    def _load(self) -> JSONValue:
        return {"url_value": self.url}


@pytest.mark.usefixtures("_reset_config")
class TestSingleSourceConfigDefaults:
    def test_load_applies_config_defaults(self) -> None:
        # Regression: single-source load() must call apply_source_config_defaults so that
        # ``configure(vault={...})`` (and ``DATURE_VAULT__*``) actually reach the source.
        configure(vault={"url": "http://from-config"})

        @dataclass
        class Config:
            url_value: str | None = None

        result = load(_ConfigAwareSource(), schema=Config)
        assert result.url_value == "http://from-config"

    def test_decorator_applies_config_defaults(self) -> None:
        configure(vault={"url": "http://from-config"})

        @load(_ConfigAwareSource())
        @dataclass
        class Config:
            url_value: str | None = None

        assert Config().url_value == "http://from-config"

    def test_validate_runs_for_single_source(self) -> None:
        # Regression: single-source path used to skip _validate(); a misconfigured VaultSource
        # would surface as a confusing failure inside _fetch() instead of a clean ValueError.
        @dataclass
        class Config:
            x: str | None = None

        with pytest.raises(ValueError, match="VaultSource: url is required"):
            load(VaultSource(path="p", token="t"), schema=Config)
