from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import Source, load
from dature.errors.exceptions import EnvVarExpandError
from dature.field_path import F
from dature.sources_loader.base import BaseLoader
from dature.sources_loader.json_ import JsonLoader
from dature.types import ExpandEnvVarsMode, FileOrStream, JSONValue


class MockLoader(BaseLoader):
    """Mock loader for testing base class functionality."""

    display_name = "mock"

    def __init__(
        self,
        *,
        prefix: str | None = None,
        test_data: JSONValue = None,
        expand_env_vars: ExpandEnvVarsMode = "default",
    ):
        super().__init__(prefix=prefix, expand_env_vars=expand_env_vars)
        self._test_data = test_data or {}

    def _load(self, path: FileOrStream) -> JSONValue:  # noqa: ARG002
        """Return test data."""
        return self._test_data


class TestBaseLoader:
    """Tests for BaseLoader base class."""

    def test_apply_prefix_simple(self):
        """Test applying simple prefix."""
        data = {"app": {"name": "Test", "port": 8080}, "other": "value"}
        loader = MockLoader(prefix="app", test_data=data)

        result = loader._apply_prefix(data)

        assert result == {"name": "Test", "port": 8080}

    def test_apply_prefix_nested(self):
        """Test applying nested prefix with dots."""
        data = {"app": {"database": {"host": "localhost", "port": 5432}}}
        loader = MockLoader(prefix="app.database", test_data=data)

        result = loader._apply_prefix(data)

        assert result == {"host": "localhost", "port": 5432}

    def test_apply_prefix_none(self):
        """Test that None prefix returns original data."""
        data = {"key": "value"}
        loader = MockLoader(test_data=data)

        result = loader._apply_prefix(data)

        assert result == data

    def test_apply_prefix_empty_string(self):
        """Test that empty string prefix returns original data."""
        data = {"key": "value"}
        loader = MockLoader(prefix="", test_data=data)

        result = loader._apply_prefix(data)

        assert result == data

    def test_apply_prefix_nonexistent(self):
        """Test applying nonexistent prefix returns empty dict."""
        data = {"app": {"name": "Test"}}
        loader = MockLoader(prefix="nonexistent", test_data=data)

        result = loader._apply_prefix(data)

        assert result == {}

    def test_apply_prefix_deep_nesting(self):
        """Test applying deeply nested prefix."""
        data = {"a": {"b": {"c": {"d": {"value": "deep"}}}}}
        loader = MockLoader(prefix="a.b.c.d", test_data=data)

        result = loader._apply_prefix(data)

        assert result == {"value": "deep"}

    def test_apply_prefix_invalid_path(self):
        """Test applying prefix with invalid path."""
        data = {"app": "not_a_dict"}
        loader = MockLoader(prefix="app.nested", test_data=data)

        result = loader._apply_prefix(data)

        assert result == {}

    def test_transform_to_dataclass(self):
        """Test transformation of data to dataclass."""

        @dataclass
        class Config:
            name: str
            port: int

        expected_data = Config(name="TestApp", port=8080)
        data = {"name": "TestApp", "port": 8080}
        loader = MockLoader(test_data=data)

        result = loader.transform_to_dataclass(data, dataclass_=Config)

        assert result == expected_data

    def test_transform_to_dataclass_with_nested(self):
        """Test transformation with nested dataclass."""

        @dataclass
        class DatabaseConfig:
            host: str
            port: int

        @dataclass
        class Config:
            database: DatabaseConfig

        expected_data = Config(database=DatabaseConfig(host="localhost", port=5432))
        data = {"database": {"host": "localhost", "port": 5432}}
        loader = MockLoader(test_data=data)

        result = loader.transform_to_dataclass(data, dataclass_=Config)

        assert result == expected_data

    def test_load_raw_and_transform(self):
        """Test load_raw + transform_to_dataclass pipeline."""

        @dataclass
        class Config:
            name: str
            port: int
            debug: bool
            default: str = "value"

        expected_data = Config(name="TestApp", port=8080, debug=True, default="value")
        data = {"app": {"name": "TestApp", "port": 8080, "debug": True}}
        loader = MockLoader(prefix="app", test_data=data)

        load_result = loader.load_raw(Path())
        result = loader.transform_to_dataclass(load_result.data, dataclass_=Config)

        assert result == expected_data

    def test_apply_prefix_with_list(self):
        """Test that apply_prefix returns data as-is when prefix points to non-dict."""
        data = {"items": [1, 2, 3]}
        loader = MockLoader(prefix="items", test_data=data)

        result = loader._apply_prefix(data)

        assert result == [1, 2, 3]


class TestNameStyleMapping:
    def test_lower_snake_to_lower_camel(self, tmp_path: Path):
        @dataclass
        class Config:
            user_name: str
            user_age: int
            is_active: bool

        json_file = tmp_path / "config.json"
        json_file.write_text('{"userName": "John", "userAge": 25, "isActive": true}')

        result = load(
            Source(file=json_file, loader=JsonLoader, name_style="lower_camel"),
            dataclass_=Config,
        )

        assert result.user_name == "John"
        assert result.user_age == 25
        assert result.is_active is True

    def test_lower_camel_to_lower_snake(self, tmp_path: Path):
        @dataclass
        class Config:
            user_name: str
            user_age: int

        json_file = tmp_path / "config.json"
        json_file.write_text('{"user_name": "Alice", "user_age": 30}')

        result = load(
            Source(file=json_file, loader=JsonLoader, name_style="lower_snake"),
            dataclass_=Config,
        )

        assert result.user_name == "Alice"
        assert result.user_age == 30

    def test_upper_camel_pascal_case(self, tmp_path: Path):
        @dataclass
        class Config:
            user_name: str
            total_count: int

        json_file = tmp_path / "config.json"
        json_file.write_text('{"UserName": "Bob", "TotalCount": 100}')

        result = load(
            Source(file=json_file, loader=JsonLoader, name_style="upper_camel"),
            dataclass_=Config,
        )

        assert result.user_name == "Bob"
        assert result.total_count == 100

    def test_lower_kebab_case(self, tmp_path: Path):
        @dataclass
        class Config:
            user_name: str
            api_key: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"user-name": "Charlie", "api-key": "secret123"}')

        result = load(
            Source(file=json_file, loader=JsonLoader, name_style="lower_kebab"),
            dataclass_=Config,
        )

        assert result.user_name == "Charlie"
        assert result.api_key == "secret123"

    def test_upper_kebab_case(self, tmp_path: Path):
        @dataclass
        class Config:
            user_name: str
            api_key: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"USER-NAME": "Dave", "API-KEY": "secret456"}')

        result = load(
            Source(file=json_file, loader=JsonLoader, name_style="upper_kebab"),
            dataclass_=Config,
        )

        assert result.user_name == "Dave"
        assert result.api_key == "secret456"

    def test_upper_snake_case(self, tmp_path: Path):
        @dataclass
        class Config:
            user_name: str
            max_retries: int

        json_file = tmp_path / "config.json"
        json_file.write_text('{"USER_NAME": "Eve", "MAX_RETRIES": 3}')

        result = load(
            Source(file=json_file, loader=JsonLoader, name_style="upper_snake"),
            dataclass_=Config,
        )

        assert result.user_name == "Eve"
        assert result.max_retries == 3


class TestFieldMapping:
    def test_simple_field_mapping(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str
            age: int
            active: bool

        json_file = tmp_path / "config.json"
        json_file.write_text('{"fullName": "John Doe", "userAge": 42, "isActive": true}')

        field_mapping = {
            F[Config].name: "fullName",
            F[Config].age: "userAge",
            F[Config].active: "isActive",
        }

        result = load(
            Source(file=json_file, loader=JsonLoader, field_mapping=field_mapping),
            dataclass_=Config,
        )

        assert result.name == "John Doe"
        assert result.age == 42
        assert result.active is True

    def test_partial_field_mapping(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str
            age: int
            city: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"userName": "Alice", "age": 28, "city": "NYC"}')

        field_mapping = {F[Config].name: "userName"}

        result = load(
            Source(file=json_file, loader=JsonLoader, field_mapping=field_mapping),
            dataclass_=Config,
        )

        assert result.name == "Alice"
        assert result.age == 28
        assert result.city == "NYC"

    def test_combined_name_style_and_field_mapping(self, tmp_path: Path):
        @dataclass
        class Config:
            user_name: str
            user_age: int
            special_field: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"userName": "Bob", "userAge": 35, "customKey": "special"}')

        field_mapping = {F[Config].special_field: "customKey"}

        result = load(
            Source(
                file=json_file,
                loader=JsonLoader,
                name_style="lower_camel",
                field_mapping=field_mapping,
            ),
            dataclass_=Config,
        )

        assert result.user_name == "Bob"
        assert result.user_age == 35
        assert result.special_field == "special"

    def test_nested_dataclass_with_field_mapping(self, tmp_path: Path):
        @dataclass
        class Address:
            city: str
            street: str

        @dataclass
        class User:
            name: str
            address: Address

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"fullName": "Charlie", "location": {"cityName": "LA", "streetName": "Main St"}}',
        )

        field_mapping = {
            F[User].name: "fullName",
            F[User].address: "location",
            F[Address].city: "cityName",
            F[Address].street: "streetName",
        }

        result = load(
            Source(file=json_file, loader=JsonLoader, field_mapping=field_mapping),
            dataclass_=User,
        )

        assert result.name == "Charlie"
        assert result.address.city == "LA"
        assert result.address.street == "Main St"

    def test_tuple_aliases_first_match_wins(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"fullName": "Alice"}')

        field_mapping = {F[Config].name: ("fullName", "userName")}

        result = load(
            Source(file=json_file, loader=JsonLoader, field_mapping=field_mapping),
            dataclass_=Config,
        )

        assert result.name == "Alice"

    def test_tuple_aliases_fallback_to_second(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"userName": "Bob"}')

        field_mapping = {F[Config].name: ("fullName", "userName")}

        result = load(
            Source(file=json_file, loader=JsonLoader, field_mapping=field_mapping),
            dataclass_=Config,
        )

        assert result.name == "Bob"

    def test_nested_field_path_resolves_owner(self, tmp_path: Path):
        @dataclass
        class Address:
            city: str

        @dataclass
        class User:
            address: Address

        json_file = tmp_path / "config.json"
        json_file.write_text('{"address": {"cityName": "LA"}}')

        field_mapping = {F[User].address.city: "cityName"}

        result = load(
            Source(file=json_file, loader=JsonLoader, field_mapping=field_mapping),
            dataclass_=User,
        )

        assert result.address.city == "LA"

    def test_string_owner_field_mapping(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"fullName": "Eve"}')

        field_mapping = {F["Config"].name: "fullName"}

        result = load(
            Source(file=json_file, loader=JsonLoader, field_mapping=field_mapping),
            dataclass_=Config,
        )

        assert result.name == "Eve"

    def test_canonical_name_takes_priority_over_alias(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Direct", "fullName": "Alias"}')

        field_mapping = {F[Config].name: "fullName"}

        result = load(
            Source(file=json_file, loader=JsonLoader, field_mapping=field_mapping),
            dataclass_=Config,
        )

        assert result.name == "Direct"

    def test_identity_map_scoped_to_owner_with_name_style(self, tmp_path: Path):
        @dataclass
        class Inner:
            user_name: str
            display_name: str

        @dataclass
        class Config:
            user_name: str
            inner: Inner

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"full_name": "Alice", "inner": {"inner_user": "Bob", "displayName": "Bobby"}}',
        )

        field_mapping = {
            F[Config].user_name: "full_name",
            F[Config].inner.user_name: "inner.inner_user",
        }

        result = load(
            Source(
                file=json_file,
                loader=JsonLoader,
                name_style="lower_camel",
                field_mapping=field_mapping,
            ),
            dataclass_=Config,
        )

        assert result.user_name == "Alice"
        assert result.inner.user_name == "Bob"
        assert result.inner.display_name == "Bobby"

    def test_identity_map_flat_json_with_name_style(self, tmp_path: Path):
        @dataclass
        class Inner:
            user_name: str
            display_name: str

        @dataclass
        class Config:
            user_name: str
            inner: Inner

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"full_name": "Alice", "inner_user": "Bob", "inner": {"displayName": "Bobby"}}',
        )

        field_mapping = {
            F[Config].user_name: "full_name",
            F[Config].inner.user_name: "inner_user",
        }

        result = load(
            Source(
                file=json_file,
                loader=JsonLoader,
                name_style="lower_camel",
                field_mapping=field_mapping,
            ),
            dataclass_=Config,
        )

        assert result.user_name == "Alice"
        assert result.inner.user_name == "Bob"
        assert result.inner.display_name == "Bobby"


class TestExpandEnvVars:
    def test_default_expands_existing(self, monkeypatch):
        monkeypatch.setenv("DATURE_TEST_HOST", "localhost")
        data = {"host": "$DATURE_TEST_HOST", "port": 8080}
        loader = MockLoader(test_data=data)

        load_result = loader.load_raw(Path())
        result = loader.transform_to_dataclass(load_result.data, dict)

        assert result == {"host": "localhost", "port": 8080}

    def test_default_keeps_missing(self, monkeypatch):
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        data = {"host": "$DATURE_MISSING", "port": 8080}
        loader = MockLoader(test_data=data)

        load_result = loader.load_raw(Path())
        result = loader.transform_to_dataclass(load_result.data, dict)

        assert result == {"host": "$DATURE_MISSING", "port": 8080}

    def test_disabled(self, monkeypatch):
        monkeypatch.setenv("DATURE_TEST_HOST", "localhost")
        data = {"host": "$DATURE_TEST_HOST", "port": 8080}
        loader = MockLoader(test_data=data, expand_env_vars="disabled")

        load_result = loader.load_raw(Path())
        result = loader.transform_to_dataclass(load_result.data, dict)

        assert result == {"host": "$DATURE_TEST_HOST", "port": 8080}

    def test_empty_replaces_missing_with_empty_string(self, monkeypatch):
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        data = {"host": "$DATURE_MISSING", "port": 8080}
        loader = MockLoader(test_data=data, expand_env_vars="empty")

        load_result = loader.load_raw(Path())
        result = loader.transform_to_dataclass(load_result.data, dict)

        assert result == {"host": "", "port": 8080}

    def test_strict_raises_on_missing(self, monkeypatch):
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        data = {"host": "$DATURE_MISSING", "port": 8080}
        loader = MockLoader(test_data=data, expand_env_vars="strict")

        with pytest.raises(EnvVarExpandError):
            loader.load_raw(Path())

    def test_strict_expands_existing(self, monkeypatch):
        monkeypatch.setenv("DATURE_TEST_HOST", "localhost")
        data = {"host": "$DATURE_TEST_HOST", "port": 8080}
        loader = MockLoader(test_data=data, expand_env_vars="strict")

        load_result = loader.load_raw(Path())
        result = loader.transform_to_dataclass(load_result.data, dict)

        assert result == {"host": "localhost", "port": 8080}
