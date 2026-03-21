"""Tests for json5_ module (Json5Loader)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError, FieldLoadError
from dature.sources_loader.json5_ import Json5Loader
from examples.all_types_dataclass import (
    EXPECTED_ALL_TYPES,
    AllPythonTypesCompact,
)
from tests.sources_loader.checker import assert_all_types_equal


class TestJson5Loader:
    """Tests for Json5Loader class."""

    def test_comprehensive_type_conversion(self, all_types_json5_file: Path):
        """Test loading JSON5 with full type coercion to dataclass."""
        result = load(LoadMetadata(file_=all_types_json5_file, loader=Json5Loader), AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_json5_with_prefix(self, prefixed_json5_file: Path):
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
            LoadMetadata(file_=prefixed_json5_file, loader=Json5Loader, prefix="app"),
            PrefixedConfig,
        )

        assert result == expected_data

    def test_json5_empty_object(self, tmp_path: Path):
        """Test loading empty JSON5 object."""
        json5_file = tmp_path / "empty.json5"
        json5_file.write_text("{}")

        loader = Json5Loader()
        data = loader._load(json5_file)

        assert data == {}

    def test_json5_env_var_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("DB_HOST", "db.example.com")
        monkeypatch.setenv("DB_PORT", "5432")

        json5_file = tmp_path / "env.json5"
        json5_file.write_text('{host: "$DB_HOST", port: "$DB_PORT"}')

        @dataclass
        class DbConfig:
            host: str
            port: int

        result = load(LoadMetadata(file_=json5_file, loader=Json5Loader), DbConfig)

        assert result.host == "db.example.com"
        assert result.port == 5432

    def test_json5_env_var_partial_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")

        json5_file = tmp_path / "env.json5"
        json5_file.write_text('{url: "http://${HOST}:${PORT}/api"}')

        @dataclass
        class Config:
            url: str

        result = load(LoadMetadata(file_=json5_file, loader=Json5Loader), Config)

        assert result.url == "http://localhost:8080/api"

    def test_json5_dollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        json5_file = tmp_path / "dollar.json5"
        json5_file.write_text('{value: "prefix$abc/suffix"}')

        @dataclass
        class Config:
            value: str

        result = load(LoadMetadata(file_=json5_file, loader=Json5Loader), Config)

        assert result.value == "prefixreplaced/suffix"

    def test_json5_dollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        json5_file = tmp_path / "dollar.json5"
        json5_file.write_text('{value: "prefix$nonexistent/suffix"}')

        @dataclass
        class Config:
            value: str

        result = load(LoadMetadata(file_=json5_file, loader=Json5Loader), Config)

        assert result.value == "prefix$nonexistent/suffix"

    def test_bool_in_int_field_raises_error(self, tmp_path: Path):
        json5_file = tmp_path / "config.json5"
        json5_file.write_text("{count: true}")

        @dataclass
        class Config:
            count: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(LoadMetadata(file_=json5_file, loader=Json5Loader), Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["count"]
        assert str(first) == (
            "  [count]  Expected int, got bool: True\n"
            f"   └── FILE '{json5_file}', line 1\n"
            f"       {json5_file.read_text()}"
        )

    def test_int_in_bool_field_raises_error(self, tmp_path: Path):
        json5_file = tmp_path / "config.json5"
        json5_file.write_text("{flag: 1}")

        @dataclass
        class Config:
            flag: bool

        with pytest.raises(DatureConfigError) as exc_info:
            load(LoadMetadata(file_=json5_file, loader=Json5Loader), Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["flag"]
        assert str(first) == (
            f"  [flag]  Expected bool, got int\n   └── FILE '{json5_file}', line 1\n       {json5_file.read_text()}"
        )
