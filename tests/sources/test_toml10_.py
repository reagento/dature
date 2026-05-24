"""Tests for toml_ module (Toml10Source)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import Toml10Source, load
from dature.errors import DatureConfigError, FieldLoadError, LineRange
from dature.sources.toml_ import _build_toml_line_map
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestToml10SourceDisplayProperties:
    def test_format_name_and_label(self):
        assert Toml10Source.format_name == "toml1.0"
        assert Toml10Source.location_label == "FILE"


class TestToml10Source:
    """Tests for Toml10Source class."""

    def test_comprehensive_type_conversion(self, all_types_toml10_file: Path):
        """Test loading TOML with full type coercion to dataclass."""
        result = load(Toml10Source(file=all_types_toml10_file), schema=AllPythonTypesCompact)

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
            Toml10Source(file=prefixed_toml_file, prefix="app"),
            schema=PrefixedConfig,
        )

        assert result == expected_data

    def test_toml_empty_file(self, tmp_path: Path):
        """Test loading empty TOML file."""
        toml_file = tmp_path / "empty.toml"
        toml_file.write_text("")

        loader = Toml10Source(file=toml_file)
        data = loader._load()

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

        result = load(Toml10Source(file=toml_file), schema=Config)

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

        result = load(Toml10Source(file=toml_file), schema=Config)

        assert result.url == "http://localhost:8080/api"

    def test_toml_dollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        toml_file = tmp_path / "dollar.toml"
        toml_file.write_text('value = "prefix$abc/suffix"')

        @dataclass
        class Config:
            value: str

        result = load(Toml10Source(file=toml_file), schema=Config)

        assert result.value == "prefixreplaced/suffix"

    def test_toml_dollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        toml_file = tmp_path / "dollar.toml"
        toml_file.write_text('value = "prefix$nonexistent/suffix"')

        @dataclass
        class Config:
            value: str

        result = load(Toml10Source(file=toml_file), schema=Config)

        assert result.value == "prefix$nonexistent/suffix"

    def test_bool_in_int_field_raises_error(self, tmp_path: Path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text("count = true")

        @dataclass
        class Config:
            count: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(Toml10Source(file=toml_file), schema=Config)

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
            load(Toml10Source(file=toml_file), schema=Config)

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


def _toml10(content: str) -> dict[tuple[str, ...], LineRange]:
    return _build_toml_line_map(content, "1.0.0")


class TestToml10FindLineRange:
    @pytest.mark.parametrize(
        ("content", "key"),
        [
            pytest.param('str1 = """\nx=1\nViolets are blue"""\nx = 1\n', ("x",), id="double_quotes"),
            pytest.param("str1 = '''\nport = 8080\n'''\nport = 3000\n", ("port",), id="single_quotes"),
        ],
    )
    def test_key_after_multiline(self, content: str, key: tuple[str, ...]):
        assert _toml10(content).get(key) == LineRange(start=4, end=4)

    def test_key_inside_multiline_not_matched_as_real_key(self):
        content = 'str1 = """\nhost = localhost\n"""\nhost = "production"\n'
        assert _toml10(content).get(("host",)) == LineRange(start=4, end=4)

    def test_key_only_inside_multiline_returns_not_found(self):
        content = 'str1 = """\nx = 1\n"""\n'
        assert _toml10(content).get(("x",)) is None

    def test_scalar_value(self):
        content = "timeout = 30\n"
        assert _toml10(content).get(("timeout",)) == LineRange(start=1, end=1)

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param('key = """\nline1\nline2\n"""\n', id="double_quotes"),
            pytest.param("key = '''\nline1\nline2\n'''\n", id="single_quotes"),
        ],
    )
    def test_multiline_string(self, content: str):
        assert _toml10(content).get(("key",)) == LineRange(start=1, end=4)

    def test_single_line_triple_quote_string(self):
        content = 'key = """single-line"""\n'
        assert _toml10(content).get(("key",)) == LineRange(start=1, end=1)

    def test_multiline_array(self):
        content = 'tags = [\n  "a",\n  "b"\n]\n'
        assert _toml10(content).get(("tags",)) == LineRange(start=1, end=4)

    def test_not_found(self):
        content = 'name = "test"\n'
        assert _toml10(content).get(("missing",)) is None

    def test_inline_array(self):
        content = 'tags = ["a", "b"]\n'
        assert _toml10(content).get(("tags",)) == LineRange(start=1, end=1)

    def test_inline_table(self):
        content = 'db = {host = "localhost", port = 5432}\n'
        assert _toml10(content).get(("db", "host")) == LineRange(start=1, end=1)

    def test_array_of_tables_nested_key(self):
        content = (
            '[[product]]\nname = "Hammer"\nsku = 738594937\n\n'
            "[[product]]\n\n"
            '[[product]]\nname = "Nail"\nsku = 284758393\n\n'
            'color = "gray"\n'
        )
        assert _toml10(content).get(("product", "0", "name")) == LineRange(start=2, end=2)
        assert _toml10(content).get(("product", "0", "sku")) == LineRange(start=3, end=3)
        assert _toml10(content).get(("product", "2", "name")) == LineRange(start=8, end=8)
        assert _toml10(content).get(("product", "2", "sku")) == LineRange(start=9, end=9)
        assert _toml10(content).get(("product", "2", "color")) == LineRange(start=11, end=11)
