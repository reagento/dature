from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path

import pytest

import dature
from dature import JsonSource, Source, load
from dature.errors import EnvVarExpandError
from dature.field_path import F
from dature.loading.merge_config import SourceParams
from dature.loading.source_loading import _apply_source_init_params
from dature.sources.base import FileFieldMixin
from dature.sources.retort import string_value_loaders, transform_to_dataclass
from dature.sources.yaml_ import Yaml12Source
from dature.types import JSONValue


@pytest.fixture(params=[StringIO("data"), BytesIO(b"data")])
def stream_fixture(request):
    return request.param


@dataclass(kw_only=True)
class MockSource(Source):
    """Mock source for testing base class functionality."""

    format_name = "mock"
    location_label = "MOCK"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        """Return test data."""
        return self.test_data


class TestBaseSource:
    """Tests for Source base class."""

    def test_apply_prefix_simple(self):
        """Test applying simple prefix."""
        data = {"app": {"name": "Test", "port": 8080}, "other": "value"}
        loader = MockSource(prefix="app", test_data=data)

        result = loader._apply_prefix(data)

        assert result == {"name": "Test", "port": 8080}

    def test_apply_prefix_nested(self):
        """Test applying nested prefix with dots."""
        data = {"app": {"database": {"host": "localhost", "port": 5432}}}
        loader = MockSource(prefix="app.database", test_data=data)

        result = loader._apply_prefix(data)

        assert result == {"host": "localhost", "port": 5432}

    def test_apply_prefix_none(self):
        """Test that None prefix returns original data."""
        data = {"key": "value"}
        loader = MockSource(test_data=data)

        result = loader._apply_prefix(data)

        assert result == data

    def test_apply_prefix_empty_string(self):
        """Test that empty string prefix returns original data."""
        data = {"key": "value"}
        loader = MockSource(prefix="", test_data=data)

        result = loader._apply_prefix(data)

        assert result == data

    def test_apply_prefix_nonexistent(self):
        """Test applying nonexistent prefix returns empty dict."""
        data = {"app": {"name": "Test"}}
        loader = MockSource(prefix="nonexistent", test_data=data)

        result = loader._apply_prefix(data)

        assert result == {}

    def test_apply_prefix_deep_nesting(self):
        """Test applying deeply nested prefix."""
        data = {"a": {"b": {"c": {"d": {"value": "deep"}}}}}
        loader = MockSource(prefix="a.b.c.d", test_data=data)

        result = loader._apply_prefix(data)

        assert result == {"value": "deep"}

    def test_apply_prefix_invalid_path(self):
        """Test applying prefix with invalid path."""
        data = {"app": "not_a_dict"}
        loader = MockSource(prefix="app.nested", test_data=data)

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
        loader = MockSource(test_data=data)

        result = transform_to_dataclass(loader, data, schema=Config)

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
        loader = MockSource(test_data=data)

        result = transform_to_dataclass(loader, data, schema=Config)

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
        loader = MockSource(prefix="app", test_data=data)

        load_result = loader.load_raw()
        result = transform_to_dataclass(loader, load_result.data, schema=Config)

        assert result == expected_data

    def test_apply_prefix_with_list(self):
        """Test that apply_prefix returns data as-is when prefix points to non-dict."""
        data = {"items": [1, 2, 3]}
        loader = MockSource(prefix="items", test_data=data)

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
            JsonSource(file=json_file, name_style="lower_camel"),
            schema=Config,
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
            JsonSource(file=json_file, name_style="lower_snake"),
            schema=Config,
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
            JsonSource(file=json_file, name_style="upper_camel"),
            schema=Config,
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
            JsonSource(file=json_file, name_style="lower_kebab"),
            schema=Config,
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
            JsonSource(file=json_file, name_style="upper_kebab"),
            schema=Config,
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
            JsonSource(file=json_file, name_style="upper_snake"),
            schema=Config,
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
            JsonSource(file=json_file, field_mapping=field_mapping),
            schema=Config,
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
            JsonSource(file=json_file, field_mapping=field_mapping),
            schema=Config,
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
            JsonSource(file=json_file, name_style="lower_camel", field_mapping=field_mapping),
            schema=Config,
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
            JsonSource(file=json_file, field_mapping=field_mapping),
            schema=User,
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
            JsonSource(file=json_file, field_mapping=field_mapping),
            schema=Config,
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
            JsonSource(file=json_file, field_mapping=field_mapping),
            schema=Config,
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
            JsonSource(file=json_file, field_mapping=field_mapping),
            schema=User,
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
            JsonSource(file=json_file, field_mapping=field_mapping),
            schema=Config,
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
            JsonSource(file=json_file, field_mapping=field_mapping),
            schema=Config,
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
            JsonSource(file=json_file, name_style="lower_camel", field_mapping=field_mapping),
            schema=Config,
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
            JsonSource(file=json_file, name_style="lower_camel", field_mapping=field_mapping),
            schema=Config,
        )

        assert result.user_name == "Alice"
        assert result.inner.user_name == "Bob"
        assert result.inner.display_name == "Bobby"


class TestExpandEnvVars:
    def test_default_expands_existing(self, monkeypatch):
        monkeypatch.setenv("DATURE_TEST_HOST", "localhost")
        data = {"host": "$DATURE_TEST_HOST", "port": 8080}
        loader = _apply_source_init_params(MockSource(test_data=data), SourceParams())

        load_result = loader.load_raw()
        result = transform_to_dataclass(loader, load_result.data, dict)

        assert result == {"host": "localhost", "port": 8080}

    def test_default_keeps_missing(self, monkeypatch):
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        data = {"host": "$DATURE_MISSING", "port": 8080}
        loader = _apply_source_init_params(MockSource(test_data=data), SourceParams())

        load_result = loader.load_raw()
        result = transform_to_dataclass(loader, load_result.data, dict)

        assert result == {"host": "$DATURE_MISSING", "port": 8080}

    def test_disabled(self, monkeypatch):
        monkeypatch.setenv("DATURE_TEST_HOST", "localhost")
        data = {"host": "$DATURE_TEST_HOST", "port": 8080}
        loader = MockSource(test_data=data, expand_env_vars="disabled")

        load_result = loader.load_raw()
        result = transform_to_dataclass(loader, load_result.data, dict)

        assert result == {"host": "$DATURE_TEST_HOST", "port": 8080}

    def test_empty_replaces_missing_with_empty_string(self, monkeypatch):
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        data = {"host": "$DATURE_MISSING", "port": 8080}
        loader = MockSource(test_data=data, expand_env_vars="empty")

        load_result = loader.load_raw()
        result = transform_to_dataclass(loader, load_result.data, dict)

        assert result == {"host": "", "port": 8080}

    def test_strict_raises_on_missing(self, monkeypatch):
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        data = {"host": "$DATURE_MISSING", "port": 8080}
        loader = MockSource(test_data=data, expand_env_vars="strict")

        with pytest.raises(EnvVarExpandError):
            loader.load_raw()

    def test_strict_expands_existing(self, monkeypatch):
        monkeypatch.setenv("DATURE_TEST_HOST", "localhost")
        data = {"host": "$DATURE_TEST_HOST", "port": 8080}
        loader = MockSource(test_data=data, expand_env_vars="strict")

        load_result = loader.load_raw()
        result = transform_to_dataclass(loader, load_result.data, dict)

        assert result == {"host": "localhost", "port": 8080}


class TestFileFieldMixin:
    @pytest.mark.parametrize(
        ("file_input", "expected_file", "expected_type"),
        [
            ("/data/test.json", "/data/test.json", str),
            (Path("/data/test.json"), str(Path("/data/test.json")), str),
            (None, None, type(None)),
        ],
    )
    def test_post_init_file_field(self, file_input, expected_file, expected_type):
        @dataclass
        class Src(FileFieldMixin):
            pass

        src = Src(file=file_input)

        assert src.file == expected_file
        assert isinstance(src.file, expected_type)

    def test_post_init_file_field_stream(self, stream_fixture):
        @dataclass
        class Src(FileFieldMixin):
            pass

        src = Src(file=stream_fixture)

        assert src.file is stream_fixture

    @pytest.mark.parametrize(
        ("file_input", "expected_type"),
        [
            ("config.json", Path),
            (Path("config.json"), Path),
            (None, Path),
        ],
    )
    def test_resolve_file_field_path_types(self, file_input, expected_type):
        result = FileFieldMixin.resolve_file_field(file_input)

        assert isinstance(result, expected_type)

    def test_resolve_file_field_stream(self, stream_fixture):
        result = FileFieldMixin.resolve_file_field(stream_fixture)

        assert result is stream_fixture

    @pytest.mark.parametrize(
        ("file_input", "expected"),
        [
            ("config.json", "config.json"),
            (Path("config.json"), "config.json"),
            ("", ""),
            (None, None),
            (StringIO("data"), "<stream>"),
            (BytesIO(b"data"), "<stream>"),
        ],
    )
    def test_file_field_display(self, file_input, expected):
        result = FileFieldMixin.file_field_display(file_input)

        assert result == expected

    @pytest.mark.parametrize(
        ("file_input", "expected"),
        [
            ("config.json", Path("config.json")),
            (Path("config.json"), Path("config.json")),
            ("", Path()),
            (None, None),
            (StringIO("data"), None),
            (BytesIO(b"data"), None),
        ],
    )
    def test_file_field_path_for_errors(self, file_input, expected):
        result = FileFieldMixin.file_field_path_for_errors(file_input)

        assert result == expected

    def test_file_display_with_resolved_path(self, tmp_path: Path):
        @dataclass
        class Src(FileFieldMixin):
            pass

        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        src = Src(file=config_file)
        assert src.file_display() == str(config_file)

    def test_file_path_for_errors_with_resolved_path(self, tmp_path: Path):
        @dataclass
        class Src(FileFieldMixin):
            pass

        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        src = Src(file=config_file)
        assert src.file_path_for_errors() == config_file


class TestStringValueLoaders:
    def test_returns_nine_providers(self):
        loaders = string_value_loaders()

        assert len(loaders) == 9


class TestResolveLocation:
    def test_file_content_none_returns_empty(self):
        locations = MockSource().resolve_location(
            field_path=["name"],
            file_content=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].line_range is None
        assert locations[0].line_content is None

    def test_empty_field_path_returns_empty(self):
        locations = MockSource().resolve_location(
            field_path=[],
            file_content='{"name": "test"}',
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].line_range is None

    def test_path_finder_none_returns_empty(self):
        locations = MockSource().resolve_location(
            field_path=["name"],
            file_content='{"name": "test"}',
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].line_range is None

    def test_json_source_finds_line_range(self, tmp_path):
        content = '{\n  "name": "test",\n  "port": 8080\n}'

        locations = JsonSource(file=tmp_path / "config.json").resolve_location(
            field_path=["name"],
            file_content=content,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].line_range is not None
        assert locations[0].line_content is not None

    def test_json_source_with_prefix(self, tmp_path):
        content = '{\n  "app": {\n    "name": "test"\n  }\n}'

        locations = JsonSource(file=tmp_path / "config.json", prefix="app").resolve_location(
            field_path=["name"],
            file_content=content,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].line_range is not None

    def test_json_source_field_not_found_returns_empty(self, tmp_path):
        content = '{\n  "name": "test"\n}'

        locations = JsonSource(file=tmp_path / "config.json").resolve_location(
            field_path=["nonexistent"],
            file_content=content,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].line_range is None


class TestFileSourceSearch:
    """Tests for FileSource system path search (FileFieldMixin._resolved_file_path)."""

    @pytest.fixture(autouse=True)
    def _reset_config(self):
        dature.configure(loading={"search_system_paths": True, "system_config_dirs": None})

    @dataclass
    class _Cfg:
        host: str
        port: int

    def test_finds_file_in_cwd(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("host: localhost\nport: 8080")

        result = dature.load(Yaml12Source(file="config.yaml"), schema=self._Cfg)

        assert result.host == "localhost"
        assert result.port == 8080

    def test_search_system_paths_disabled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        system_dir = tmp_path / "system_config"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: system\nport: 9000")
        (tmp_path / "config.yaml").write_text("host: cwd\nport: 1000")

        dature.configure(
            loading={"search_system_paths": False, "system_config_dirs": (system_dir,)},
        )

        result = dature.load(Yaml12Source(file="config.yaml"), schema=self._Cfg)

        assert result.host == "cwd"
        assert result.port == 1000

    def test_finds_in_custom_dirs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        custom_dir = tmp_path / "custom_config"
        custom_dir.mkdir()
        (custom_dir / "app.yaml").write_text("host: custom\nport: 3000")

        result = dature.load(
            Yaml12Source(file="app.yaml", system_config_dirs=(custom_dir,)),
            schema=self._Cfg,
        )

        assert result.host == "custom"
        assert result.port == 3000

    def test_priority_cwd_before_system(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.json").write_text('{"host": "cwd", "port": 1111}')
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.json").write_text('{"host": "system", "port": 2222}')

        result = dature.load(
            JsonSource(file="config.json", system_config_dirs=(system_dir,)),
            schema=self._Cfg,
        )

        assert result.host == "cwd"
        assert result.port == 1111

    def test_disable_search_per_source(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: system\nport: 5000")
        (tmp_path / "config.yaml").write_text("host: cwd\nport: 1000")

        result = dature.load(
            Yaml12Source(
                file="config.yaml",
                search_system_paths=False,
                system_config_dirs=(system_dir,),
            ),
            schema=self._Cfg,
        )

        assert result.host == "cwd"
        assert result.port == 1000

    def test_enable_search_per_source_when_global_disabled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        dature.configure(loading={"search_system_paths": False})

        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: enabled\nport: 6000")

        result = dature.load(
            Yaml12Source(
                file="config.yaml",
                search_system_paths=True,
                system_config_dirs=(system_dir,),
            ),
            schema=self._Cfg,
        )

        assert result.host == "enabled"
        assert result.port == 6000
