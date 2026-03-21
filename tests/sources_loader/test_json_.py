"""Tests for json_ module (JsonLoader)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError, FieldLoadError
from dature.sources_loader.json_ import JsonLoader
from examples.all_types_dataclass import (
    EXPECTED_ALL_TYPES,
    AllPythonTypesCompact,
)
from tests.sources_loader.checker import assert_all_types_equal


class TestJsonLoader:
    """Tests for JsonLoader class."""

    def test_comprehensive_type_conversion(self, all_types_json_file: Path):
        """Test loading JSON with full type coercion to dataclass."""
        result = load(LoadMetadata(file_=all_types_json_file, loader=JsonLoader), AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_json_with_prefix(self, prefixed_json_file: Path):
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
            LoadMetadata(file_=prefixed_json_file, loader=JsonLoader, prefix="app"),
            PrefixedConfig,
        )

        assert result == expected_data

    def test_json_empty_object(self, tmp_path: Path):
        """Test loading empty JSON object."""
        json_file = tmp_path / "empty.json"
        json_file.write_text("{}")

        loader = JsonLoader()
        data = loader._load(json_file)

        assert data == {}

    def test_json_env_var_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("DB_HOST", "db.example.com")
        monkeypatch.setenv("DB_PORT", "5432")

        json_file = tmp_path / "env.json"
        json_file.write_text('{"host": "$DB_HOST", "port": "$DB_PORT"}')

        @dataclass
        class DbConfig:
            host: str
            port: int

        result = load(LoadMetadata(file_=json_file, loader=JsonLoader), DbConfig)

        assert result.host == "db.example.com"
        assert result.port == 5432

    def test_json_env_var_partial_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")

        json_file = tmp_path / "env.json"
        json_file.write_text('{"url": "http://${HOST}:${PORT}/api"}')

        @dataclass
        class Config:
            url: str

        result = load(LoadMetadata(file_=json_file, loader=JsonLoader), Config)

        assert result.url == "http://localhost:8080/api"

    def test_json_dollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        json_file = tmp_path / "dollar.json"
        json_file.write_text('{"value": "prefix$abc/suffix"}')

        @dataclass
        class Config:
            value: str

        result = load(LoadMetadata(file_=json_file, loader=JsonLoader), Config)

        assert result.value == "prefixreplaced/suffix"

    def test_json_dollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        json_file = tmp_path / "dollar.json"
        json_file.write_text('{"value": "prefix$nonexistent/suffix"}')

        @dataclass
        class Config:
            value: str

        result = load(LoadMetadata(file_=json_file, loader=JsonLoader), Config)

        assert result.value == "prefix$nonexistent/suffix"

    def test_bool_in_int_field_raises_error(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"count": true}')

        @dataclass
        class Config:
            count: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(LoadMetadata(file_=json_file, loader=JsonLoader), Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["count"]
        assert str(first) == (
            "  [count]  Expected int, got bool: True\n"
            f"   └── FILE '{json_file}', line 1\n"
            f"       {json_file.read_text()}"
        )

    def test_int_in_bool_field_raises_error(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"flag": 1}')

        @dataclass
        class Config:
            flag: bool

        with pytest.raises(DatureConfigError) as exc_info:
            load(LoadMetadata(file_=json_file, loader=JsonLoader), Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["flag"]
        assert str(first) == (
            f"  [flag]  Expected bool, got int\n   └── FILE '{json_file}', line 1\n       {json_file.read_text()}"
        )
