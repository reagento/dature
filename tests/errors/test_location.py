from pathlib import Path

from dature.errors import LineRange
from dature.errors.location import ErrorContext, resolve_source_location
from dature.sources_loader.env_ import EnvFileLoader, EnvLoader
from dature.sources_loader.json_ import JsonLoader
from dature.sources_loader.toml_ import Toml11Loader


class TestResolveSourceLocation:
    def test_env_source(self):
        ctx = ErrorContext(
            dataclass_name="Config",
            loader_class=EnvLoader,
            file_path=None,
            prefix="APP_",
            split_symbols="__",
        )
        locs = resolve_source_location(["database", "port"], ctx, filecontent=None)
        assert len(locs) == 1
        assert locs[0].display_label == "ENV"
        assert locs[0].env_var_name == "APP_DATABASE__PORT"
        assert locs[0].file_path is None

    def test_env_source_no_prefix(self):
        ctx = ErrorContext(
            dataclass_name="Config",
            loader_class=EnvLoader,
            file_path=None,
            prefix=None,
            split_symbols="__",
        )
        locs = resolve_source_location(["timeout"], ctx, filecontent=None)
        assert locs[0].env_var_name == "TIMEOUT"

    def test_env_source_custom_split_symbols(self):
        ctx = ErrorContext(
            dataclass_name="Config",
            loader_class=EnvLoader,
            file_path=None,
            prefix="APP_",
            split_symbols="_",
        )
        locs = resolve_source_location(["database", "port"], ctx, filecontent=None)
        assert locs[0].env_var_name == "APP_DATABASE_PORT"

    def test_json_source_with_line(self):
        content = '{\n  "timeout": "30",\n  "name": "test"\n}'
        ctx = ErrorContext(
            dataclass_name="Config",
            loader_class=JsonLoader,
            file_path=Path("config.json"),
            prefix=None,
            split_symbols="__",
        )
        locs = resolve_source_location(["timeout"], ctx, filecontent=content)
        assert locs[0].display_label == "FILE"
        assert locs[0].line_range == LineRange(start=2, end=2)
        assert locs[0].line_content == ['"timeout": "30",']

    def test_toml_source_with_line(self):
        content = 'timeout = "30"\nname = "test"'
        ctx = ErrorContext(
            dataclass_name="Config",
            loader_class=Toml11Loader,
            file_path=Path("config.toml"),
            prefix=None,
            split_symbols="__",
        )
        locs = resolve_source_location(["timeout"], ctx, filecontent=content)
        assert locs[0].display_label == "FILE"
        assert locs[0].line_range == LineRange(start=1, end=1)
        assert locs[0].line_content == ['timeout = "30"']

    def test_envfilesource(self):
        content = "# comment\nAPP_TIMEOUT=30\nAPP_NAME=test"
        ctx = ErrorContext(
            dataclass_name="Config",
            loader_class=EnvFileLoader,
            file_path=Path(".env"),
            prefix="APP_",
            split_symbols="__",
        )
        locs = resolve_source_location(["timeout"], ctx, filecontent=content)
        assert locs[0].display_label == "ENV FILE"
        assert locs[0].env_var_name == "APP_TIMEOUT"
        assert locs[0].line_range == LineRange(start=2, end=2)
        assert locs[0].line_content == ["APP_TIMEOUT=30"]

    def test_filesource_does_not_mask_non_secret_field(self):
        content = '{\n  "password": "secret123",\n  "timeout": "30"\n}'
        ctx = ErrorContext(
            dataclass_name="Config",
            loader_class=JsonLoader,
            file_path=Path("config.json"),
            prefix=None,
            split_symbols="__",
            secret_paths=frozenset({"password"}),
        )
        locs = resolve_source_location(["timeout"], ctx, filecontent=content)
        assert locs[0].line_content == ['"timeout": "30"']

    def test_filesource_masks_secret_field(self):
        content = '{\n  "password": "secret123",\n  "timeout": "30"\n}'
        ctx = ErrorContext(
            dataclass_name="Config",
            loader_class=JsonLoader,
            file_path=Path("config.json"),
            prefix=None,
            split_symbols="__",
            secret_paths=frozenset({"password"}),
        )
        locs = resolve_source_location(["password"], ctx, filecontent=content)
        assert locs[0].line_content == ['"password": "<REDACTED>",']

    def test_filesource_masks_line_when_secret_on_same_line(self):
        content = '{"password": "secret123", "timeout": "30"}'
        ctx = ErrorContext(
            dataclass_name="Config",
            loader_class=JsonLoader,
            file_path=Path("config.json"),
            prefix=None,
            split_symbols="__",
            secret_paths=frozenset({"password"}),
        )
        locs = resolve_source_location(["timeout"], ctx, filecontent=content)
        assert locs[0].line_content == ['{"password": "<REDACTED>", "timeout": "30"}']
