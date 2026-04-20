"""Tests for env_ module (EnvSource and EnvFileSource)."""

from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pytest

from dature import EnvFileSource, EnvSource, load
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestEnvFileSource:
    """Tests for EnvFileSource class."""

    def test_prefix_filtering(self, prefixed_env_file: Path):
        """Test prefix filtering with nested structures."""
        loader = EnvFileSource(file=prefixed_env_file, prefix="APP_")
        result = loader.load_raw()

        assert result.data == {
            "name": "PrefixedApp",
            "environment": "production",
            "database": {
                "host": "prod.db.com",
                "port": 5432,
            },
        }

    def test_custom_split_symbols(self, custom_separator_env_file: Path):
        """Test custom separator for nested keys."""
        loader = EnvFileSource(file=custom_separator_env_file, prefix="APP_", nested_sep=".")
        result = loader.load_raw()

        assert result.data == {
            "name": "CustomApp",
            "environment": "development",
            "db": {
                "host": "dev.db.com",
                "port": 5432,
            },
        }

    def test_comprehensive_type_conversion(self, all_types_env_file: Path):
        """Test loading ENV with full type coercion to dataclass."""
        result = load(EnvFileSource(file=all_types_env_file), schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_empty_file(self, tmp_path: Path):
        """Test loading empty .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        loader = EnvFileSource(file=env_file)
        data = loader._load()

        assert data == {}

    def test_env_fileenv_var_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("BASE_URL", "https://api.example.com")

        env_file = tmp_path / ".env"
        env_file.write_text("api_url=$BASE_URL/v1\nbase=$BASE_URL")

        @dataclass
        class Config:
            api_url: str
            base: str

        result = load(EnvFileSource(file=env_file), schema=Config)

        assert result.api_url == "https://api.example.com/v1"
        assert result.base == "https://api.example.com"

    def test_env_fileenv_var_partial_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")

        env_file = tmp_path / ".env"
        env_file.write_text("url=http://${HOST}:${PORT}/api")

        @dataclass
        class Config:
            url: str

        result = load(EnvFileSource(file=env_file), schema=Config)

        assert result.url == "http://localhost:8080/api"

    def test_env_filedollar_sign_mid_string_existing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("abc", "replaced")

        env_file = tmp_path / ".env"
        env_file.write_text("value=prefix$abc/suffix")

        @dataclass
        class Config:
            value: str

        result = load(EnvFileSource(file=env_file), schema=Config)

        assert result.value == "prefixreplaced/suffix"

    @pytest.mark.parametrize(
        ("raw_value", "expected"),
        [
            ('"hello"', "hello"),
            ("'hello'", "hello"),
            ('""hello""', '"hello"'),
            ("''hello''", "'hello'"),
            ("\"'hello'\"", "'hello'"),
            ("'\"hello\"'", '"hello"'),
            ("\"hello'", "\"hello'"),
            ("'hello\"", "'hello\""),
            ("hello", "hello"),
            ('""', ""),
            ("''", ""),
            ('"', '"'),
            ("'", "'"),
        ],
    )
    def test_quote_stripping(self, tmp_path: Path, raw_value: str, expected: str):
        env_file = tmp_path / ".env"
        env_file.write_text(f"value={raw_value}")

        loader = EnvFileSource(file=env_file)
        data = loader._load()

        assert data == {"value": expected}

    def test_env_filedollar_sign_mid_string_missing_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("nonexistent", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text("value=prefix$nonexistent/suffix")

        @dataclass
        class Config:
            value: str

        result = load(EnvFileSource(file=env_file), schema=Config)

        assert result.value == "prefix$nonexistent/suffix"


class TestEnvSource:
    """Tests for EnvSource class."""

    def test_comprehensive_type_conversion(self, monkeypatch):
        """Test loading from os.environ with full type coercion to dataclass."""
        env_vars = {
            # Scalars
            "APP_STRING_VALUE": "hello world",
            "APP_INTEGER_VALUE": "42",
            "APP_FLOAT_VALUE": "3.14159",
            "APP_BOOLEAN_VALUE": "true",
            "APP_NONE_VALUE": "",
            # Numeric
            "APP_DECIMAL_VALUE": "3.14159265358979323846264338327950288",
            "APP_FLOAT_INF": "inf",
            "APP_FLOAT_NAN": "nan",
            # Date/time
            "APP_DATE_VALUE": "2024-01-15",
            "APP_DATETIME_VALUE": "2024-01-15T10:30:00",
            "APP_DATETIME_VALUE_WITH_TIMEZONE": "2024-01-15T10:30:00+03:00",
            "APP_DATETIME_VALUE_WITH_Z_TIMEZONE": "2024-01-15T10:30:00Z",
            "APP_TIME_VALUE": "10:30:00",
            "APP_TIMEDELTA_VALUE_WITH_DAY": "1 day, 2:30:00",
            "APP_TIMEDELTA_VALUE_WITHOUT_DAY": "2:30:00",
            "APP_TIMEDELTA_VALUE_WITHOUT_SECONDS": "2:30",
            # Lists
            "APP_LIST_STRINGS": '["item1","item2","item3"]',
            "APP_LIST_INTEGERS": "[1,2,3,4,5]",
            "APP_LIST_MIXED": '["string",42,3.14,true,null]',
            "APP_LIST_NESTED": '[["a","b"],["c","d"]]',
            "APP_LIST_DICTS": '[{"name":"Alice","age":30},{"name":"Bob","age":25}]',
            # Tuples
            "APP_TUPLE_SIMPLE": "[1,2,3]",
            "APP_TUPLE_MIXED": '["text",42,true]',
            "APP_TUPLE_NESTED": '[[1,2,3],["a","b","c"]]',
            # Sets
            "APP_SET_INTEGERS": "[1,2,3,4,5]",
            "APP_SET_STRINGS": '["apple","banana","cherry"]',
            # Dicts
            "APP_DICT_SIMPLE__KEY1": "value1",
            "APP_DICT_SIMPLE__KEY2": "value2",
            "APP_DICT_MIXED__STRING": "text",
            "APP_DICT_MIXED__NUMBER": "42",
            "APP_DICT_MIXED__FLOAT": "3.14",
            "APP_DICT_MIXED__BOOL": "true",
            "APP_DICT_MIXED__LIST": "[1,2,3]",
            "APP_DICT_NESTED__LEVEL1__LEVEL2__LEVEL3": "deep_value",
            "APP_DICT_INT_KEYS__1": "one",
            "APP_DICT_INT_KEYS__2": "two",
            "APP_DICT_INT_KEYS__3": "three",
            "APP_DICT_LIST_DICT": (
                '{"users":[{"name":"Alice","role":"admin"},{"name":"Bob","role":"user"}],'
                '"teams":[{"name":"backend","size":5}]}'
            ),
            # Binary/encoding
            "APP_BYTES_VALUE": "binary data",
            "APP_BYTEARRAY_VALUE": "binary",
            "APP_COMPLEX_VALUE": "1+2j",
            "APP_BASE64URL_BYTES_VALUE": "SGVsbG8gV29ybGQ=",
            "APP_BASE64URL_STR_VALUE": "c2VjcmV0IHRva2Vu",
            # Custom fields
            "APP_SECRET_STR_VALUE": "supersecret123",
            "APP_PAYMENT_CARD_NUMBER_VALUE": "4111111111111111",
            "APP_BYTE_SIZE_VALUE": "1.5 GB",
            # Paths
            "APP_PATH_VALUE": "/usr/local/bin",
            "APP_PURE_POSIX_PATH_VALUE": "/etc/hosts",
            "APP_PURE_WINDOWS_PATH_VALUE": "C:/Windows/System32",
            # Network
            "APP_IPV4_ADDRESS_VALUE": "192.168.1.1",
            "APP_IPV6_ADDRESS_VALUE": "2001:db8::1",
            "APP_IPV4_NETWORK_VALUE": "192.168.1.0/24",
            "APP_IPV6_NETWORK_VALUE": "2001:db8::/32",
            "APP_IPV4_INTERFACE_VALUE": "192.168.1.1/24",
            "APP_IPV6_INTERFACE_VALUE": "2001:db8::1/32",
            # Identifiers
            "APP_UUID_VALUE": "550e8400-e29b-41d4-a716-446655440000",
            "APP_URL_VALUE": "https://example.com/path?query=value#fragment",
            # Edge cases
            "APP_EMPTY_STRING": "",
            "APP_EMPTY_LIST": "[]",
            "APP_EMPTY_DICT": "{}",
            "APP_ZERO_INT": "0",
            "APP_ZERO_FLOAT": "0.0",
            "APP_FALSE_BOOL": "false",
            # Union/optional
            "APP_OPTIONAL_STRING": "",
            "APP_UNION_TYPE": "42",
            "APP_NESTED_OPTIONAL": '[{"name":"Alice","email":"alice@example.com"},{"name":"Bob","email":null}]',
            "APP_RANGE_VALUES": "[0,2,4,6,8]",
            "APP_FROZENSET_VALUE": "[1,2,3,4,5]",
            # Nested dataclasses in collections
            "APP_NESTED_DC_SINGLE__CITY": "Moscow",
            "APP_NESTED_DC_SINGLE__ZIP_CODE": "101000",
            "APP_NESTED_DC_LIST": '[{"name":"urgent","priority":1},{"name":"low","priority":5}]',
            "APP_NESTED_DC_DICT": (
                '{"home":{"city":"Berlin","zip_code":"10115"},"work":{"city":"Paris","zip_code":"75001"}}'
            ),
            "APP_NESTED_DC_TUPLE": '[{"name":"bug","priority":2},{"name":"feature","priority":3}]',
            # Enum/Flag/Literal
            "APP_ENUM_VALUE": "green",
            "APP_FLAG_VALUE": "3",
            "APP_LITERAL_VALUE": "info",
            # Additional stdlib types
            "APP_REGEX_PATTERN": "^[a-z]+$",
            "APP_FRACTION_VALUE": "1/3",
            "APP_DEQUE_VALUE": '["first","second","third"]',
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        result = load(EnvSource(prefix="APP_"), schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_prefix_filtering(self, monkeypatch):
        """Test that only variables with prefix are loaded."""
        monkeypatch.setenv("APP_VAR", "included")
        monkeypatch.setenv("OTHER_VAR", "excluded")
        monkeypatch.setenv("APP_KEY", "also_included")

        @dataclass
        class TestConfig:
            var: str
            key: str

        expected_data = TestConfig(var="included", key="also_included")

        data = load(EnvSource(prefix="APP_"), schema=TestConfig)

        assert data == expected_data

    def test_custom_split_symbols(self, monkeypatch):
        """Test custom separator for nested keys."""
        monkeypatch.setenv("APP_DB.HOST", "localhost")
        monkeypatch.setenv("APP_DB.PORT", "5432")

        @dataclass
        class TestData:
            host: str
            port: str

        @dataclass
        class TestConfig:
            db: TestData

        expected_data = TestConfig(db=TestData(host="localhost", port="5432"))

        data = load(
            EnvSource(prefix="APP_", nested_sep="."),
            schema=TestConfig,
        )

        assert data == expected_data
        assert data == expected_data
        assert data == expected_data


class TestEnvSourceDisplayProperties:
    def test_format_name_and_label(self):
        assert EnvSource.format_name == "env"
        assert EnvSource.location_label == "ENV"


class TestEnvFileSourceDisplayProperties:
    def test_format_name_and_label(self):
        assert EnvFileSource.format_name == "envfile"
        assert EnvFileSource.location_label == "ENV FILE"


class TestEnvSourceResolveLocation:
    def test_resolve_returns_env_var_name(self):
        locations = EnvSource().resolve_location(
            field_path=["host"],
            file_content=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].env_var_name == "HOST"
        assert locations[0].file_path is None
        assert locations[0].location_label == "ENV"

    def test_resolve_with_prefix(self):
        locations = EnvSource(prefix="APP_").resolve_location(
            field_path=["host"],
            file_content=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].env_var_name == "APP_HOST"

    def test_resolve_nested_path(self):
        locations = EnvSource().resolve_location(
            field_path=["database", "host"],
            file_content=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].env_var_name == "DATABASE__HOST"

    def test_resolve_with_custom_split_symbols(self):
        locations = EnvSource(nested_sep=".").resolve_location(
            field_path=["database", "host"],
            file_content=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].env_var_name == "DATABASE.HOST"


class TestEnvFileSourceResolveLocation:
    def test_resolve_finds_line_in_content(self):
        content = "HOST=localhost\nPORT=8080"

        locations = EnvFileSource(file=".env").resolve_location(
            field_path=["port"],
            file_content=content,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].env_var_name == "PORT"
        assert locations[0].line_range is not None
        assert locations[0].line_range.start == 2

    def test_resolve_no_content(self):
        locations = EnvFileSource(file=".env").resolve_location(
            field_path=["host"],
            file_content=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].line_range is None
        assert locations[0].location_label == "ENV FILE"


class TestEnvFileSourceStream:
    def test_load_from_string_stream(self):
        @dataclass
        class Config:
            name: str
            port: int

        result = load(EnvFileSource(file=StringIO("NAME=test\nPORT=8080")), schema=Config)

        assert result.name == "test"
        assert result.port == 8080
