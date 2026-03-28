"""Tests for toml_ module (Toml10Loader)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import Source, load
from dature.errors.exceptions import DatureConfigError, FieldLoadError
from dature.sources_loader.toml_ import Toml10Loader
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources_loader.checker import assert_all_types_equal


class TestToml10Loader:
    """Tests for Toml10Loader class."""

    def test_comprehensive_type_conversion(self, all_types_toml10_file: Path):
        """Test loading TOML with full type coercion to dataclass."""
        result = load(Source(file=all_types_toml10_file, loader=Toml10Loader), dataclass_=AllPythonTypesCompact)

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
            Source(file=prefixed_toml_file, loader=Toml10Loader, prefix="app"),
            dataclass_=PrefixedConfig,
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

        result = load(Source(file=toml_file, loader=Toml10Loader), dataclass_=Config)

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

        result = load(Source(file=toml_file, loader=Toml10Loader), dataclass_=Config)

        assert result.url == "http://localhost:8080/api"

    def test_toml_dollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        toml_file = tmp_path / "dollar.toml"
        toml_file.write_text('value = "prefix$abc/suffix"')

        @dataclass
        class Config:
            value: str

        result = load(Source(file=toml_file, loader=Toml10Loader), dataclass_=Config)

        assert result.value == "prefixreplaced/suffix"

    def test_toml_dollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        toml_file = tmp_path / "dollar.toml"
        toml_file.write_text('value = "prefix$nonexistent/suffix"')

        @dataclass
        class Config:
            value: str

        result = load(Source(file=toml_file, loader=Toml10Loader), dataclass_=Config)

        assert result.value == "prefix$nonexistent/suffix"

    def test_bool_in_int_field_raises_error(self, tmp_path: Path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text("count = true")

        @dataclass
        class Config:
            count: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(Source(file=toml_file, loader=Toml10Loader), dataclass_=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["count"]
        assert str(first) == (
            f"  [count]  Expected int, got bool\n"
            f"   ├── count = true\n"
            f"   │           ^^^^\n"
            f"   └── FILE '{toml_file}', line 1"
        )

    def test_int_in_bool_field_raises_error(self, tmp_path: Path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text("flag = 1")

        @dataclass
        class Config:
            flag: bool

        with pytest.raises(DatureConfigError) as exc_info:
            load(Source(file=toml_file, loader=Toml10Loader), dataclass_=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["flag"]
        assert str(first) == (
            f"  [flag]  Expected bool, got int\n"
            f"   ├── flag = 1\n"
            f"   │          ^\n"
            f"   └── FILE '{toml_file}', line 1"
        )  # fmt: skip
