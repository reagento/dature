"""Tests for loading/single.py."""

from dataclasses import dataclass
from enum import Flag
from io import BytesIO, StringIO
from pathlib import Path

import pytest

from dature.loading.single import load_as_function, make_decorator
from dature.metadata import Source
from dature.sources_loader.env_ import EnvFileLoader
from dature.sources_loader.json_ import JsonLoader


class TestMakeDecorator:
    def test_not_dataclass_raises(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')
        metadata = Source(file=json_file)

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
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
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str

        original_init = Config.__init__
        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        assert Config.__init__ is not original_init

    def test_patches_post_init(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        assert hasattr(Config, "__post_init__")

    def test_loads_on_init(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "from_file", "port": 8080}')
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
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
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
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
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
            cache=True,
            debug=False,
        )
        result = decorator(Config)

        assert result is Config

    def test_preserves_original_post_init(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')
        metadata = Source(file=json_file)

        post_init_called = []

        @dataclass
        class Config:
            name: str

            def __post_init__(self):
                post_init_called.append(True)

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
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
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
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
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
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
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
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
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str
            port: int

        result = load_as_function(
            loader_instance=JsonLoader(),
            file_path=json_file,
            dataclass_=Config,
            metadata=metadata,
            debug=False,
        )

        assert result.name == "test"
        assert result.port == 3000

    def test_with_prefix(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"app": {"name": "nested"}}')
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str

        result = load_as_function(
            loader_instance=JsonLoader(prefix="app"),
            file_path=json_file,
            dataclass_=Config,
            metadata=metadata,
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
        metadata = Source(file=env_file, loader=EnvFileLoader)

        @dataclass
        class Config:
            name: str
            perms: _Permission

        result = load_as_function(
            loader_instance=EnvFileLoader(),
            file_path=env_file,
            dataclass_=Config,
            metadata=metadata,
            debug=False,
        )

        assert result.perms == _Permission.READ | _Permission.WRITE

    def test_flag_from_json_as_int(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "perms": 3}')
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str
            perms: _Permission

        result = load_as_function(
            loader_instance=JsonLoader(),
            file_path=json_file,
            dataclass_=Config,
            metadata=metadata,
            debug=False,
        )

        assert result.perms == _Permission.READ | _Permission.WRITE


class TestCoerceFlagFieldsDecoratorMode:
    def test_flag_from_env_file(self, tmp_path: Path):
        env_file = tmp_path / "config.env"
        env_file.write_text("NAME=test\nPERMS=5\n")
        metadata = Source(file=env_file, loader=EnvFileLoader)

        @dataclass
        class Config:
            name: str
            perms: _Permission

        decorator = make_decorator(
            loader_instance=EnvFileLoader(),
            file_path=env_file,
            metadata=metadata,
            cache=True,
            debug=False,
        )
        decorator(Config)

        config = Config()
        assert config.perms == _Permission.READ | _Permission.EXECUTE

    def test_flag_from_json_as_int(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "perms": 7}')
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str
            perms: _Permission

        decorator = make_decorator(
            loader_instance=JsonLoader(),
            file_path=json_file,
            metadata=metadata,
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
        metadata = Source(file=stream, loader=JsonLoader)

        @dataclass
        class Config:
            name: str
            port: int

        result = load_as_function(
            loader_instance=JsonLoader(),
            file_path=stream,
            dataclass_=Config,
            metadata=metadata,
            debug=False,
        )

        assert result.name == "test"
        assert result.port == 3000

    def test_path_object_directly(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "direct_path"}')
        metadata = Source(file=json_file)

        @dataclass
        class Config:
            name: str

        result = load_as_function(
            loader_instance=JsonLoader(),
            file_path=json_file,
            dataclass_=Config,
            metadata=metadata,
            debug=False,
        )

        assert result.name == "direct_path"
