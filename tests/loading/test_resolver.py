from collections.abc import Buffer
from dataclasses import dataclass
from io import BytesIO, RawIOBase, StringIO
from pathlib import Path

import pytest

from dature.field_path import F
from dature.loading.resolver import resolve_loader, resolve_loader_class
from dature.metadata import LoadMetadata
from dature.sources_loader.docker_secrets import DockerSecretsLoader
from dature.sources_loader.env_ import EnvFileLoader, EnvLoader
from dature.sources_loader.ini_ import IniLoader
from dature.sources_loader.json5_ import Json5Loader
from dature.sources_loader.json_ import JsonLoader
from dature.sources_loader.toml_ import Toml11Loader
from dature.sources_loader.yaml_ import Yaml11Loader, Yaml12Loader


class _DummyRawIO(RawIOBase):
    def readinto(self, b: Buffer) -> int:  # noqa: ARG002
        return 0


class TestResolveLoaderClass:
    def test_explicit_loader(self) -> None:
        assert resolve_loader_class(loader=Yaml11Loader, file_="config.json") is Yaml11Loader

    def test_no_file_returns_env(self) -> None:
        assert resolve_loader_class(loader=None, file_=None) is EnvLoader

    @pytest.mark.parametrize(
        ("extension", "expected"),
        [
            (".env", EnvFileLoader),
            (".yaml", Yaml12Loader),
            (".yml", Yaml12Loader),
            (".json", JsonLoader),
            (".json5", Json5Loader),
            (".toml", Toml11Loader),
            (".ini", IniLoader),
            (".cfg", IniLoader),
        ],
    )
    def test_extension_mapping(self, extension: str, expected: type) -> None:
        assert resolve_loader_class(loader=None, file_=f"config{extension}") is expected

    @pytest.mark.parametrize(
        "filename",
        [".env.local", ".env.development", ".env.production"],
    )
    def test_dotenv_patterns(self, filename: str) -> None:
        assert resolve_loader_class(loader=None, file_=filename) is EnvFileLoader

    def test_unknown_extension_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot determine loader type"):
            resolve_loader_class(loader=None, file_="config.xyz")

    def test_uppercase_extension(self) -> None:
        assert resolve_loader_class(loader=None, file_="config.JSON") is JsonLoader

    def test_env_loader_with_file_raises(self) -> None:
        with pytest.raises(ValueError, match="EnvLoader reads from environment variables") as exc_info:
            resolve_loader_class(loader=EnvLoader, file_="config.json")

        assert str(exc_info.value) == (
            "EnvLoader reads from environment variables and does not use files. "
            "Remove file_ or use a file-based loader instead (e.g. EnvFileLoader)."
        )

    def test_env_file_loader_with_file_allowed(self) -> None:
        assert resolve_loader_class(loader=EnvFileLoader, file_=".env.local") is EnvFileLoader

    def test_directory_returns_docker_secrets(self, tmp_path) -> None:
        assert resolve_loader_class(loader=None, file_=tmp_path) is DockerSecretsLoader


class TestMissingOptionalDependency:
    @pytest.mark.parametrize(
        ("extension", "extra", "blocked_module"),
        [
            (".toml", "toml", "toml_rs"),
            (".yaml", "yaml", "ruamel"),
            (".yml", "yaml", "ruamel"),
            (".json5", "json5", "json5"),
        ],
    )
    def test_missing_extra_raises_helpful_error(
        self,
        extension,
        extra,
        blocked_module,
        block_import,
    ) -> None:
        with block_import(blocked_module):
            with pytest.raises(ImportError) as exc_info:
                resolve_loader_class(loader=None, file_=f"config{extension}")

            assert str(exc_info.value) == (
                f"To use '{extension}' files, install the '{extra}' extra: pip install dature[{extra}]"
            )


class TestResolveLoader:
    def test_returns_correct_loader_type(self) -> None:
        metadata = LoadMetadata(file_="config.json")

        loader = resolve_loader(metadata)

        assert isinstance(loader, JsonLoader)

    def test_passes_prefix(self) -> None:
        metadata = LoadMetadata(prefix="APP_")

        loader = resolve_loader(metadata)

        assert loader._prefix == "APP_"

    def test_passes_name_style(self) -> None:
        metadata = LoadMetadata(file_="config.json", name_style="lower_snake")

        loader = resolve_loader(metadata)

        assert loader._name_style == "lower_snake"

    def test_passes_field_mapping(self) -> None:
        @dataclass
        class Config:
            key: str

        mapping = {F[Config].key: "value"}
        metadata = LoadMetadata(file_="config.json", field_mapping=mapping)

        loader = resolve_loader(metadata)

        assert loader._field_mapping == mapping

    def test_default_metadata_returns_env_loader(self) -> None:
        metadata = LoadMetadata()

        loader = resolve_loader(metadata)

        assert isinstance(loader, EnvLoader)

    def test_env_with_file_path(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=VALUE")
        metadata = LoadMetadata(file_=env_file)

        loader = resolve_loader(metadata)

        assert isinstance(loader, EnvFileLoader)


class TestFilelikeResolverValidation:
    @pytest.mark.parametrize("stream", [StringIO(), BytesIO(), _DummyRawIO()])
    def test_file_like_without_loader_raises(self, stream) -> None:
        with pytest.raises(TypeError) as exc_info:
            resolve_loader_class(loader=None, file_=stream)

        assert str(exc_info.value) == (
            "Cannot determine loader type for a file-like object. "
            "Please specify loader explicitly (e.g. loader=JsonLoader)."
        )

    @pytest.mark.parametrize("stream", [StringIO(), BytesIO(), _DummyRawIO()])
    def test_file_like_with_env_loader_raises(self, stream) -> None:
        with pytest.raises(ValueError, match="EnvLoader does not support file-like objects") as exc_info:
            resolve_loader_class(loader=EnvLoader, file_=stream)

        assert str(exc_info.value) == (
            "EnvLoader does not support file-like objects. "
            "Use a file-based loader (e.g. JsonLoader, TomlLoader) with file-like objects."
        )

    @pytest.mark.parametrize("stream", [StringIO(), BytesIO(), _DummyRawIO()])
    def test_file_like_with_docker_secrets_loader_raises(self, stream) -> None:
        with pytest.raises(ValueError, match="DockerSecretsLoader does not support file-like objects") as exc_info:
            resolve_loader_class(loader=DockerSecretsLoader, file_=stream)

        assert str(exc_info.value) == (
            "DockerSecretsLoader does not support file-like objects. "
            "Use a file-based loader (e.g. JsonLoader, TomlLoader) with file-like objects."
        )

    @pytest.mark.parametrize("stream", [StringIO(), BytesIO(), _DummyRawIO()])
    def test_file_like_with_explicit_loader_allowed(self, stream) -> None:
        assert resolve_loader_class(loader=JsonLoader, file_=stream) is JsonLoader
