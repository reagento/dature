"""Tests for yaml_ module (Yaml11Source)."""

from dataclasses import dataclass
from pathlib import Path

import pytest
from ruamel.yaml.docinfo import Version

from dature import Yaml11Source, load
from dature.errors import DatureConfigError, FieldLoadError, LineRange
from dature.sources.yaml_ import _build_yaml_line_map
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestYaml11SourceDisplayProperties:
    def test_format_name_and_label(self):
        assert Yaml11Source.format_name == "yaml1.1"
        assert Yaml11Source.location_label == "FILE"


class TestYaml11Source:
    """Tests for Yaml11Source class."""

    def test_comprehensive_type_conversion(self, all_types_yaml11_file: Path):
        """Test loading YAML with full type coercion to dataclass."""
        result = load(Yaml11Source(file=all_types_yaml11_file), schema=AllPythonTypesCompact)

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
            Yaml11Source(file=prefixed_yaml_file, prefix="app"),
            schema=PrefixedConfig,
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
            Yaml11Source(file=yaml_config_with_env_vars_file),
            schema=EnvConfig,
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

        result = load(Yaml11Source(file=yaml_file), schema=Config)

        assert result.url == "http://localhost:8080/api"

    def test_yaml_dollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        yaml_file = tmp_path / "dollar.yaml"
        yaml_file.write_text("value: prefix$abc/suffix")

        @dataclass
        class Config:
            value: str

        result = load(Yaml11Source(file=yaml_file), schema=Config)

        assert result.value == "prefixreplaced/suffix"

    def test_yaml_dollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        yaml_file = tmp_path / "dollar.yaml"
        yaml_file.write_text("value: prefix$nonexistent/suffix")

        @dataclass
        class Config:
            value: str

        result = load(Yaml11Source(file=yaml_file), schema=Config)

        assert result.value == "prefix$nonexistent/suffix"

    def test_yaml_empty_file(self, tmp_path: Path):
        """Test loading empty YAML file."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        loader = Yaml11Source(file=yaml_file)
        data = loader._load()

        assert data is None

    def test_bool_in_int_field_raises_error(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("count: true")

        @dataclass
        class Config:
            count: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(Yaml11Source(file=yaml_file), schema=Config)

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
            load(Yaml11Source(file=yaml_file), schema=Config)

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


def _yaml11(content: str) -> dict[tuple[str, ...], LineRange]:
    return _build_yaml_line_map(content, Version(1, 1))


class TestYaml11FindLineRange:
    def test_key_after_literal_block(self):
        content = "str1: |\n  x: 1\n  Violets are blue\nx: 1\n"
        assert _yaml11(content).get(("x",)) == LineRange(start=4, end=4)

    def test_key_after_folded_block(self):
        content = "str1: >\n  host: localhost\n  more text\nhost: production\n"
        assert _yaml11(content).get(("host",)) == LineRange(start=4, end=4)

    def test_scalar_value(self):
        content = "timeout: 30\n"
        assert _yaml11(content).get(("timeout",)) == LineRange(start=1, end=1)

    def test_multiline_dict(self):
        content = "db:\n  host: localhost\n  port: 5432\n"
        assert _yaml11(content).get(("db",)) == LineRange(start=1, end=3)

    def test_multiline_list(self):
        content = "tags:\n  - a\n  - b\n"
        assert _yaml11(content).get(("tags",)) == LineRange(start=1, end=3)

    def test_literal_block_scalar(self):
        content = "key: |\n  line1\n  line2\n"
        assert _yaml11(content).get(("key",)) == LineRange(start=1, end=3)

    def test_folded_block_scalar(self):
        content = "key: >\n  line1\n  line2\n"
        assert _yaml11(content).get(("key",)) == LineRange(start=1, end=3)

    def test_block_scalar_with_strip_modifier(self):
        content = "key: |-\n  line1\n  line2\n"
        assert _yaml11(content).get(("key",)) == LineRange(start=1, end=3)

    def test_block_scalar_with_keep_modifier(self):
        content = "key: >+\n  line1\n  line2\n"
        assert _yaml11(content).get(("key",)) == LineRange(start=1, end=3)

    def test_not_found(self):
        content = "name: test\n"
        assert _yaml11(content).get(("missing",)) is None

    def test_inline_value(self):
        content = "name: test\n"
        assert _yaml11(content).get(("name",)) == LineRange(start=1, end=1)
