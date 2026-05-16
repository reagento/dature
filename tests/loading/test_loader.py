"""Unit tests for src/dature/loading/loader.py — the public ``Loader`` class."""

from dataclasses import dataclass
from datetime import timedelta
from enum import Flag
from io import BytesIO, StringIO
from pathlib import Path

import pytest
import time_machine

from dature import EnvFileSource, JsonSource, Loader, Source


@dataclass
class _Config:
    host: str
    port: int


class TestLoaderValidation:
    def test_no_sources_raises(self) -> None:
        with pytest.raises(TypeError, match="at least one Source"):
            Loader(schema=_Config)

    def test_non_source_argument_raises(self) -> None:
        with pytest.raises(TypeError, match="must be Source instances"):
            Loader("not a source", schema=_Config)

    def test_negative_timedelta_raises(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "x", "port": 1}')
        with pytest.raises(ValueError, match="cache timedelta must be non-negative"):
            Loader(JsonSource(file=json_file), schema=_Config, cache=timedelta(seconds=-1))


class TestLoaderLoad:
    def test_returns_loaded_dataclass(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 3000}')

        result = Loader(JsonSource(file=json_file), schema=_Config).load()

        assert result.host == "h"
        assert result.port == 3000

    def test_with_prefix(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"app": {"host": "nested", "port": 1}}')

        @dataclass
        class Config:
            host: str
            port: int

        result = Loader(JsonSource(file=json_file, prefix="app"), schema=Config).load()

        assert result.host == "nested"
        assert result.port == 1


class TestLoaderCache:
    def test_cache_true_repeats_same_instance(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=True)

        first = loader.load()
        second = loader.load()

        assert first is second

    def test_cache_false_reloads_every_call(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=False)

        first = loader.load()
        second = loader.load()

        assert first is not second

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
    def test_loader_cache_matrix(
        self,
        tmp_path: Path,
        time_control: time_machine.Traveller,
        cache_arg: bool | timedelta,
        advance_seconds: float,
        expected_second: str,
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "original", "port": 8080}')
        source = JsonSource(file=json_file)

        @dataclass
        class Config:
            host: str
            port: int

        loader = Loader(source, schema=Config, cache=cache_arg)
        first = loader.load()
        json_file.write_text('{"host": "updated", "port": 9090}')
        time_control.shift(advance_seconds)
        second = loader.load()

        assert first.host == "original"
        assert second.host == expected_second

    def test_invalidate_forces_reload(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "original", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=True)

        first = loader.load()
        json_file.write_text('{"host": "updated", "port": 1}')
        loader.invalidate()
        second = loader.load()

        assert first.host == "original"
        assert second.host == "updated"

    def test_invalidate_when_empty_is_noop(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=True)
        loader.invalidate()  # no entry yet — must not raise
        assert loader.load().host == "h"

    def test_loader_per_schema_independent(self, tmp_path: Path) -> None:
        a_file = tmp_path / "a.json"
        a_file.write_text('{"name": "A"}')
        source = JsonSource(file=a_file)

        @dataclass
        class ConfigA:
            name: str

        @dataclass
        class ConfigB:
            name: str

        first_a = Loader(source, schema=ConfigA, cache=True).load()
        first_b = Loader(source, schema=ConfigB, cache=True).load()

        assert first_a.name == "A"
        assert first_b.name == "A"
        assert type(first_a).__name__ == "ConfigA"
        assert type(first_b).__name__ == "ConfigB"

    def test_loader_different_sources_independent(self, tmp_path: Path) -> None:
        a_file = tmp_path / "a.json"
        a_file.write_text('{"name": "A"}')
        b_file = tmp_path / "b.json"
        b_file.write_text('{"name": "B"}')

        source_a = JsonSource(file=a_file)
        source_b = JsonSource(file=b_file)

        @dataclass
        class Config:
            name: str

        cfg_a = Loader(source_a, schema=Config, cache=True).load()
        cfg_b = Loader(source_b, schema=Config, cache=True).load()

        assert cfg_a.name == "A"
        assert cfg_b.name == "B"


class TestLoaderMulti:
    def test_two_sources_merge(self, tmp_path: Path) -> None:
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')
        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        loader = Loader(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=_Config,
            cache=True,
        )
        cfg = loader.load()

        assert cfg.host == "localhost"
        assert cfg.port == 8080

    def test_multi_cache_hits_within_loader(self, tmp_path: Path) -> None:
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')
        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        loader = Loader(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=_Config,
            cache=True,
        )
        first = loader.load()
        defaults.write_text('{"host": "changed", "port": 3000}')
        second = loader.load()

        assert first is second


class TestLoaderAsDecorator:
    def test_not_dataclass_raises(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        decorator = Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)

        with pytest.raises(TypeError, match="must be a dataclass"):

            @decorator
            class NotADataclass:
                pass

    def test_patches_init(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        @dataclass
        class Config:
            name: str

        original_init = Config.__init__
        Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)

        assert Config.__init__ is not original_init

    def test_patches_post_init(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        @dataclass
        class Config:
            name: str

        Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)

        assert hasattr(Config, "__post_init__")

    def test_loads_on_init(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "from_file", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)

        config = Config()
        assert config.name == "from_file"
        assert config.port == 8080

    def test_init_args_override_loaded(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "from_file", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)

        config = Config(name="overridden")
        assert config.name == "overridden"
        assert config.port == 8080

    def test_returns_same_class(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        @dataclass
        class Config:
            name: str

        result = Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)

        assert result is Config

    def test_preserves_original_post_init(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        post_init_called: list[bool] = []

        @dataclass
        class Config:
            name: str

            def __post_init__(self) -> None:
                post_init_called.append(True)

        Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)

        Config()
        assert len(post_init_called) == 1


class TestLoaderAsDecoratorCache:
    @pytest.mark.parametrize(
        ("cache_arg", "first_name", "second_name_expected"),
        [
            (True, "original", "original"),
            (False, "original", "updated"),
        ],
        ids=["cache_true", "cache_false"],
    )
    def test_cache_behavior(
        self,
        tmp_path: Path,
        cache_arg: bool,
        first_name: str,
        second_name_expected: str,
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        Loader.as_decorator(JsonSource(file=json_file), cache=cache_arg, debug=False)(Config)

        first = Config()
        json_file.write_text('{"name": "updated", "port": 9090}')
        second = Config()

        assert first.name == first_name
        assert second.name == second_name_expected

    def test_cache_allows_override(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)

        first = Config()
        assert first.name == "original"
        assert first.port == 8080

        second = Config(name="overridden")
        assert second.name == "overridden"
        assert second.port == 8080


class _Permission(Flag):
    READ = 1
    WRITE = 2
    EXECUTE = 4


class TestLoaderFlagFields:
    @pytest.mark.parametrize(
        ("source_factory_name", "perms_value", "expected"),
        [
            ("env_file", "3", _Permission.READ | _Permission.WRITE),
            ("json", 3, _Permission.READ | _Permission.WRITE),
        ],
        ids=["env-file", "json-int"],
    )
    def test_function_mode(
        self,
        tmp_path: Path,
        source_factory_name: str,
        perms_value: object,
        expected: _Permission,
    ) -> None:
        @dataclass
        class Config:
            name: str
            perms: _Permission

        source: Source
        if source_factory_name == "env_file":
            env_file = tmp_path / "config.env"
            env_file.write_text(f"NAME=test\nPERMS={perms_value}\n")
            source = EnvFileSource(file=env_file)
        else:
            json_file = tmp_path / "config.json"
            json_file.write_text(f'{{"name": "test", "perms": {perms_value}}}')
            source = JsonSource(file=json_file)

        result = Loader(source, schema=Config, debug=False).load()
        assert result.perms == expected

    @pytest.mark.parametrize(
        ("source_factory_name", "perms_value", "expected"),
        [
            ("env_file", "5", _Permission.READ | _Permission.EXECUTE),
            ("json", 7, _Permission.READ | _Permission.WRITE | _Permission.EXECUTE),
        ],
        ids=["env-file", "json-int"],
    )
    def test_decorator_mode(
        self,
        tmp_path: Path,
        source_factory_name: str,
        perms_value: object,
        expected: _Permission,
    ) -> None:
        @dataclass
        class Config:
            name: str
            perms: _Permission

        source: Source
        if source_factory_name == "env_file":
            env_file = tmp_path / "config.env"
            env_file.write_text(f"NAME=test\nPERMS={perms_value}\n")
            source = EnvFileSource(file=env_file)
        else:
            json_file = tmp_path / "config.json"
            json_file.write_text(f'{{"name": "test", "perms": {perms_value}}}')
            source = JsonSource(file=json_file)

        Loader.as_decorator(source, cache=True, debug=False)(Config)
        assert Config().perms == expected


class TestLoaderFilelikeSources:
    @pytest.mark.parametrize(
        "stream",
        [
            BytesIO(b'{"name": "test", "port": 3000}'),
            StringIO('{"name": "test", "port": 3000}'),
        ],
        ids=["bytes-io", "string-io"],
    )
    def test_json_from_filelike(self, stream: BytesIO | StringIO) -> None:
        @dataclass
        class Config:
            name: str
            port: int

        result = Loader(JsonSource(file=stream), schema=Config, debug=False).load()
        assert result.name == "test"
        assert result.port == 3000

    def test_path_object_directly(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "direct_path"}')

        @dataclass
        class Config:
            name: str

        result = Loader(JsonSource(file=json_file), schema=Config, debug=False).load()
        assert result.name == "direct_path"
