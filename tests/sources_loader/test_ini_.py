"""Tests for ini_ module (IniLoader)."""

import configparser
from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import Source, load
from dature.sources_loader.ini_ import IniLoader
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources_loader.checker import assert_all_types_equal


class TestIniLoader:
    """Tests for IniLoader class."""

    def test_comprehensive_type_conversion(self, all_types_ini_file: Path):
        """Test loading INI with full type coercion to dataclass."""
        result = load(
            Source(file=all_types_ini_file, loader=IniLoader, prefix="all_types"),
            dataclass_=AllPythonTypesCompact,
        )

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_ini_sections(self, ini_sections_file: Path):
        """Test INI sections and DEFAULT inheritance."""
        loader = IniLoader()
        data = loader._load(ini_sections_file)

        assert data == {
            "DEFAULT": {
                "app_name": "TestApp",
            },
            "app": {
                "app_name": "MyApp",
                "port": "8080",
            },
            "database": {
                "host": "localhost",
                "app_name": "TestApp",
            },
        }

    def test_ini_with_prefix(self, prefixed_ini_file: Path):
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
            Source(file=prefixed_ini_file, loader=IniLoader, prefix="app"),
            dataclass_=PrefixedConfig,
        )

        assert result == expected_data

    def test_ini_requires_sections(self, tmp_path: Path):
        """Test that INI format requires section headers."""
        ini_file = tmp_path / "nosection.ini"
        ini_file.write_text("key = value")

        loader = IniLoader()

        with pytest.raises(configparser.MissingSectionHeaderError):
            loader._load(ini_file)

    def test_ini_env_var_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("DB_HOST", "db.example.com")
        monkeypatch.setenv("DB_PORT", "5432")

        ini_file = tmp_path / "env.ini"
        ini_file.write_text("[database]\nhost = $DB_HOST\nport = $DB_PORT")

        @dataclass
        class DbConfig:
            host: str
            port: int

        result = load(
            Source(file=ini_file, loader=IniLoader, prefix="database"),
            dataclass_=DbConfig,
        )

        assert result.host == "db.example.com"
        assert result.port == 5432

    def test_ini_env_var_partial_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")

        ini_file = tmp_path / "env.ini"
        ini_file.write_text("[section]\nurl = http://${HOST}:${PORT}/api")

        @dataclass
        class Config:
            url: str

        result = load(
            Source(file=ini_file, loader=IniLoader, prefix="section"),
            dataclass_=Config,
        )

        assert result.url == "http://localhost:8080/api"

    def test_ini_dollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        ini_file = tmp_path / "env.ini"
        ini_file.write_text("[section]\nvalue = prefix$abc/suffix")

        @dataclass
        class Config:
            value: str

        result = load(
            Source(file=ini_file, loader=IniLoader, prefix="section"),
            dataclass_=Config,
        )

        assert result.value == "prefixreplaced/suffix"

    def test_ini_dollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        ini_file = tmp_path / "env.ini"
        ini_file.write_text("[section]\nvalue = prefix$nonexistent/suffix")

        @dataclass
        class Config:
            value: str

        result = load(
            Source(file=ini_file, loader=IniLoader, prefix="section"),
            dataclass_=Config,
        )

        assert result.value == "prefix$nonexistent/suffix"
