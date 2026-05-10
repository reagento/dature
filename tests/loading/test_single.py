"""Tests for loading/single.py."""

from dataclasses import dataclass
from enum import Flag
from io import BytesIO, StringIO
from pathlib import Path
from typing import ClassVar

import pytest

from dature import EnvFileSource, JsonSource, VaultSource, configure, load
from dature.loading.single import load_as_function, make_decorator
from dature.sources.base import Source
from dature.types import JSONValue


class TestMakeDecorator:
    def test_not_dataclass_raises(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')
        metadata = JsonSource(file=json_file)

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )

        with pytest.raises(TypeError, match="must be a dataclass"):

            @decorator
            class NotADataclass:
                pass

    def test_patches_init(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str

        original_init = Config.__init__
        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        assert Config.__init__ is not original_init

    def test_patches_post_init(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        assert hasattr(Config, "__post_init__")

    def test_loads_on_init(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "from_file", "port": 8080}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        config = Config()
        assert config.name == "from_file"
        assert config.port == 8080

    def test_init_args_override_loaded(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "from_file", "port": 8080}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        config = Config(name="overridden")
        assert config.name == "overridden"
        assert config.port == 8080

    def test_returns_same_class(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        result = decorator(Config)

        assert result is Config

    def test_preserves_original_post_init(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')
        metadata = JsonSource(file=json_file)

        post_init_called = []

        @dataclass
        class Config:
            name: str

            def __post_init__(self):
                post_init_called.append(True)

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        Config()
        assert len(post_init_called) == 1


class TestCache:
    def test_cache_returns_same_data(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        first = Config()
        json_file.write_text('{"name": "updated", "port": 9090}')
        second = Config()

        assert first.name == "original"
        assert second.name == "original"
        assert second.port == 8080

    def test_no_cache_rereads_file(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            source=metadata,
            cache=False,
            debug=False,
        )
        decorator(Config)

        first = Config()
        json_file.write_text('{"name": "updated", "port": 9090}')
        second = Config()

        assert first.name == "original"
        assert second.name == "updated"
        assert second.port == 9090

    def test_cache_allows_override(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        first = Config()
        assert first.name == "original"
        assert first.port == 8080

        second = Config(name="overridden")
        assert second.name == "overridden"
        assert second.port == 8080


class TestLoadAsFunction:
    def test_returns_loaded_dataclass(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "port": 3000}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        result = load_as_function(
            source=metadata,
            schema=Config,
            debug=False,
        )

        assert result.name == "test"
        assert result.port == 3000

    def test_with_prefix(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"app": {"name": "nested"}}')
        metadata = JsonSource(file=json_file, prefix="app")

        @dataclass
        class Config:
            name: str

        result = load_as_function(
            source=metadata,
            schema=Config,
            debug=False,
        )

        assert result.name == "nested"


class _Permission(Flag):
    READ = 1
    WRITE = 2
    EXECUTE = 4


class TestCoerceFlagFieldsFunctionMode:
    def test_flag_from_env_file(self, tmp_path: Path):
        env_file = tmp_path / "config.env"
        env_file.write_text("NAME=test\nPERMS=3\n")
        metadata = EnvFileSource(file=env_file)

        @dataclass
        class Config:
            name: str
            perms: _Permission

        result = load_as_function(
            source=metadata,
            schema=Config,
            debug=False,
        )

        assert result.perms == _Permission.READ | _Permission.WRITE

    def test_flag_from_json_as_int(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "perms": 3}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            perms: _Permission

        result = load_as_function(
            source=metadata,
            schema=Config,
            debug=False,
        )

        assert result.perms == _Permission.READ | _Permission.WRITE


class TestCoerceFlagFieldsDecoratorMode:
    def test_flag_from_env_file(self, tmp_path: Path):
        env_file = tmp_path / "config.env"
        env_file.write_text("NAME=test\nPERMS=5\n")
        metadata = EnvFileSource(file=env_file)

        @dataclass
        class Config:
            name: str
            perms: _Permission

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        config = Config()
        assert config.perms == _Permission.READ | _Permission.EXECUTE

    def test_flag_from_json_as_int(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "perms": 7}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str
            perms: _Permission

        decorator = make_decorator(
            source=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        config = Config()
        assert config.perms == _Permission.READ | _Permission.WRITE | _Permission.EXECUTE


class TestFilelikeLoadAsFunction:
    @pytest.mark.parametrize(
        "stream",
        [
            BytesIO(b'{"name": "test", "port": 3000}'),
            StringIO('{"name": "test", "port": 3000}'),
        ],
    )
    def test_json_from_filelike(self, stream) -> None:
        metadata = JsonSource(file=stream)

        @dataclass
        class Config:
            name: str
            port: int

        result = load_as_function(
            source=metadata,
            schema=Config,
            debug=False,
        )

        assert result.name == "test"
        assert result.port == 3000

    def test_path_object_directly(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "direct_path"}')
        metadata = JsonSource(file=json_file)

        @dataclass
        class Config:
            name: str

        result = load_as_function(
            source=metadata,
            schema=Config,
            debug=False,
        )

        assert result.name == "direct_path"


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
    def test_load_applies_config_defaults(self):
        # Regression: single-source load() must call apply_source_config_defaults so that
        # ``configure(vault={...})`` (and ``DATURE_VAULT__*``) actually reach the source.
        configure(vault={"url": "http://from-config"})

        @dataclass
        class Config:
            url_value: str | None = None

        result = load(_ConfigAwareSource(), schema=Config)
        assert result.url_value == "http://from-config"

    def test_decorator_applies_config_defaults(self):
        configure(vault={"url": "http://from-config"})

        @load(_ConfigAwareSource())
        @dataclass
        class Config:
            url_value: str | None = None

        assert Config().url_value == "http://from-config"

    def test_validate_runs_for_single_source(self):
        # Regression: single-source path used to skip _validate(); a misconfigured VaultSource
        # would surface as a confusing failure inside _fetch() instead of a clean ValueError.
        @dataclass
        class Config:
            x: str | None = None

        with pytest.raises(ValueError, match="VaultSource: url is required"):
            load(VaultSource(path="p", token="t"), schema=Config)
