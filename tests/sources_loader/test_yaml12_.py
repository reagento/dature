"""Tests for yaml_ module (Yaml12Loader)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import Source, load
from dature.errors.exceptions import DatureConfigError, FieldLoadError
from dature.sources_loader.yaml_ import Yaml12Loader
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources_loader.checker import assert_all_types_equal


class TestYaml12Loader:
    """Tests for Yaml12Loader class."""

    def test_comprehensive_type_conversion(self, all_types_yaml12_file: Path):
        """Test loading YAML with full type coercion to dataclass."""
        result = load(Source(file=all_types_yaml12_file, loader=Yaml12Loader), dataclass_=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_yaml_with_prefix(self, prefixed_yaml_file: Path):
        @dataclass
        class PrefixedConfig:
            name: str
            port: int
            debug: bool
            environment: str

        expected_data = PrefixedConfig(
            name="PrefixedApp",
            port=9000,
            debug=False,
            environment="production",
        )

        result = load(
            Source(file=prefixed_yaml_file, loader=Yaml12Loader, prefix="app"),
            dataclass_=PrefixedConfig,
        )

        assert result == expected_data

    def test_yaml_env_var_substitution(self, yaml_config_with_env_vars_file: Path, monkeypatch):
        """Test YAML environment variable substitution."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
        monkeypatch.setenv("SECRET_KEY", "my_secret")
        monkeypatch.setenv("REDIS_HOST", "redis.local")
        monkeypatch.setenv("QUEUE_HOST", "queue.local")

        @dataclass
        class Services:
            cache: dict[str, str]
            queue: dict[str, str]

        @dataclass
        class EnvConfig:
            database_url: str
            secret_key: str
            services: Services

        result = load(
            Source(file=yaml_config_with_env_vars_file, loader=Yaml12Loader),
            dataclass_=EnvConfig,
        )

        assert result.database_url == "postgresql://localhost/db"
        assert result.secret_key == "my_secret"
        assert result.services.cache == {"host": "redis.local"}
        assert result.services.queue == {"host": "queue.local"}

    def test_yaml_env_var_partial_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")

        yaml_file = tmp_path / "env.yaml"
        yaml_file.write_text('url: "http://${HOST}:${PORT}/api"')

        @dataclass
        class Config:
            url: str

        result = load(Source(file=yaml_file, loader=Yaml12Loader), dataclass_=Config)

        assert result.url == "http://localhost:8080/api"

    def test_yaml_dollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        yaml_file = tmp_path / "dollar.yaml"
        yaml_file.write_text("value: prefix$abc/suffix")

        @dataclass
        class Config:
            value: str

        result = load(Source(file=yaml_file, loader=Yaml12Loader), dataclass_=Config)

        assert result.value == "prefixreplaced/suffix"

    def test_yaml_dollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        yaml_file = tmp_path / "dollar.yaml"
        yaml_file.write_text("value: prefix$nonexistent/suffix")

        @dataclass
        class Config:
            value: str

        result = load(Source(file=yaml_file, loader=Yaml12Loader), dataclass_=Config)

        assert result.value == "prefix$nonexistent/suffix"

    def test_yaml_empty_file(self, tmp_path: Path):
        """Test loading empty YAML file."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        loader = Yaml12Loader()
        data = loader._load(yaml_file)

        assert data is None

    def test_bool_in_int_field_raises_error(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("count: true")

        @dataclass
        class Config:
            count: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(Source(file=yaml_file, loader=Yaml12Loader), dataclass_=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["count"]
        assert str(first) == (
            f"  [count]  Expected int, got bool\n"
            f"   ├── count: true\n"
            f"   │          ^^^^\n"
            f"   └── FILE '{yaml_file}', line 1"
        )

    def test_int_in_bool_field_raises_error(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("flag: 1")

        @dataclass
        class Config:
            flag: bool

        with pytest.raises(DatureConfigError) as exc_info:
            load(Source(file=yaml_file, loader=Yaml12Loader), dataclass_=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["flag"]
        assert str(first) == (
            f"  [flag]  Expected bool, got int\n"
            f"   ├── flag: 1\n"
            f"   │         ^\n"
            f"   └── FILE '{yaml_file}', line 1"
        )  # fmt: skip
