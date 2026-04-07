"""Tests for json_ module (JsonSource)."""

from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pytest

from dature import JsonSource, load
from dature.errors import DatureConfigError, FieldLoadError
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestJsonSource:
    """Tests for JsonSource class."""

    def test_comprehensive_type_conversion(self, all_types_json_file: Path):
        """Test loading JSON with full type coercion to dataclass."""
        result = load(JsonSource(file=all_types_json_file), schema=AllPythonTypesCompact)

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
            JsonSource(file=prefixed_json_file, prefix="app"),
            schema=PrefixedConfig,
        )

        assert result == expected_data

    def test_json_empty_object(self, tmp_path: Path):
        """Test loading empty JSON object."""
        json_file = tmp_path / "empty.json"
        json_file.write_text("{}")

        loader = JsonSource(file=json_file)
        data = loader._load()

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

        result = load(JsonSource(file=json_file), schema=DbConfig)

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

        result = load(JsonSource(file=json_file), schema=Config)

        assert result.url == "http://localhost:8080/api"

    def test_json_dollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        json_file = tmp_path / "dollar.json"
        json_file.write_text('{"value": "prefix$abc/suffix"}')

        @dataclass
        class Config:
            value: str

        result = load(JsonSource(file=json_file), schema=Config)

        assert result.value == "prefixreplaced/suffix"

    def test_json_dollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        json_file = tmp_path / "dollar.json"
        json_file.write_text('{"value": "prefix$nonexistent/suffix"}')

        @dataclass
        class Config:
            value: str

        result = load(JsonSource(file=json_file), schema=Config)

        assert result.value == "prefix$nonexistent/suffix"

    def test_bool_in_int_field_raises_error(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"count": true}')

        @dataclass
        class Config:
            count: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(JsonSource(file=json_file), schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["count"]
        assert str(first) == (
            f"  [count]  Expected int, got bool\n"
            f"   ├── {json_file.read_text()}\n"
            f"   │             ^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_int_in_bool_field_raises_error(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"flag": 1}')

        @dataclass
        class Config:
            flag: bool

        with pytest.raises(DatureConfigError) as exc_info:
            load(JsonSource(file=json_file), schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["flag"]
        assert str(first) == (
            f"  [flag]  Expected bool, got int\n"
            f"   ├── {json_file.read_text()}\n"
            f"   │            ^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestJsonSourceDisplayProperties:
    def test_format_name_and_label(self):
        assert JsonSource.format_name == "json"
        assert JsonSource.location_label == "FILE"


class TestJsonSourceStream:
    def test_load_from_string_stream(self):
        @dataclass
        class Config:
            name: str
            port: int

        result = load(JsonSource(file=StringIO('{"name": "test", "port": 8080}')), schema=Config)

        assert result.name == "test"
        assert result.port == 8080
