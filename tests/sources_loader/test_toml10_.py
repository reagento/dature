"""Tests for toml_ module (Toml10Loader)."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.sources_loader.toml_ import Toml10Loader
from examples.all_types_dataclass import (
    EXPECTED_ALL_TYPES,
    AllPythonTypesCompact,
)
from tests.sources_loader.checker import assert_all_types_equal


class TestToml10Loader:
    """Tests for Toml10Loader class."""

    def test_comprehensive_type_conversion(self, all_types_toml10_file: Path):
        """Test loading TOML with full type coercion to dataclass."""
        result = load(LoadMetadata(file_=all_types_toml10_file, loader=Toml10Loader), AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_toml_with_prefix(self, prefixed_toml_file: Path):
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
            LoadMetadata(file_=prefixed_toml_file, loader=Toml10Loader, prefix="app"),
            PrefixedConfig,
        )

        assert result == expected_data

    def test_toml_empty_file(self, tmp_path: Path):
        """Test loading empty TOML file."""
        toml_file = tmp_path / "empty.toml"
        toml_file.write_text("")

        loader = Toml10Loader()
        data = loader._load(toml_file)

        assert data == {}

    def test_toml_env_var_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("APP_NAME", "MyApp")
        monkeypatch.setenv("APP_PORT", "9090")

        toml_file = tmp_path / "env.toml"
        toml_file.write_text('name = "$APP_NAME"\nport = "$APP_PORT"')

        @dataclass
        class Config:
            name: str
            port: int

        result = load(LoadMetadata(file_=toml_file, loader=Toml10Loader), Config)

        assert result.name == "MyApp"
        assert result.port == 9090

    def test_toml_env_var_partial_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")

        toml_file = tmp_path / "env.toml"
        toml_file.write_text('url = "http://${HOST}:${PORT}/api"')

        @dataclass
        class Config:
            url: str

        result = load(LoadMetadata(file_=toml_file, loader=Toml10Loader), Config)

        assert result.url == "http://localhost:8080/api"

    def test_toml_dollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        toml_file = tmp_path / "dollar.toml"
        toml_file.write_text('value = "prefix$abc/suffix"')

        @dataclass
        class Config:
            value: str

        result = load(LoadMetadata(file_=toml_file, loader=Toml10Loader), Config)

        assert result.value == "prefixreplaced/suffix"

    def test_toml_dollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        toml_file = tmp_path / "dollar.toml"
        toml_file.write_text('value = "prefix$nonexistent/suffix"')

        @dataclass
        class Config:
            value: str

        result = load(LoadMetadata(file_=toml_file, loader=Toml10Loader), Config)

        assert result.value == "prefix$nonexistent/suffix"
