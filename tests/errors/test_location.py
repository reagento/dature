import pytest

from dature import EnvFileSource, EnvSource, JsonSource, Toml11Source
from dature.config import MaskingConfig
from dature.errors import LineRange
from dature.errors.location import ErrorContext, resolve_source_location

_NO_MASKING = MaskingConfig(masking_mode="none")
_SECRETS_ONLY = MaskingConfig(masking_mode="secrets_only")


class TestResolveSourceLocation:
    def test_env_source(self):
        ctx = ErrorContext(
            dataclass_name="Config",
            source=EnvSource(prefix="APP_"),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["database", "port"], ctx, file_content=None)
        assert len(locs) == 1
        assert locs[0].location_label == "ENV"
        assert locs[0].env_var_name == "APP_DATABASE__PORT"
        assert locs[0].file_path is None

    def test_env_source_shows_value(self, monkeypatch):
        monkeypatch.setenv("APP_PORT", "abc")
        ctx = ErrorContext(
            dataclass_name="Config",
            source=EnvSource(prefix="APP_"),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["port"], ctx, file_content=None)
        assert locs[0].env_var_value == "abc"

    def test_env_source_no_value_when_unset(self):
        ctx = ErrorContext(
            dataclass_name="Config",
            source=EnvSource(prefix="APP_"),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["port"], ctx, file_content=None)
        assert locs[0].env_var_value is None

    def test_env_source_secret_drops_value(self, monkeypatch):
        monkeypatch.setenv("APP_TOKEN", "hunter2")
        ctx = ErrorContext(
            dataclass_name="Config",
            source=EnvSource(prefix="APP_"),
            secret_paths=frozenset({"token"}),
            masking=_SECRETS_ONLY,
        )
        locs = resolve_source_location(["token"], ctx, file_content=None)
        assert locs[0].env_var_value is None

    def test_env_source_none_mode_keeps_secret_value(self, monkeypatch):
        """masking_mode="none" means no masking at all, even for a declared secret path."""
        monkeypatch.setenv("APP_TOKEN", "hunter2")
        ctx = ErrorContext(
            dataclass_name="Config",
            source=EnvSource(prefix="APP_"),
            secret_paths=frozenset({"token"}),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["token"], ctx, file_content=None)
        assert locs[0].env_var_value == "hunter2"

    def test_env_source_no_prefix(self):
        ctx = ErrorContext(
            dataclass_name="Config",
            source=EnvSource(),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["timeout"], ctx, file_content=None)
        assert locs[0].env_var_name == "TIMEOUT"

    def test_env_source_custom_split_symbols(self):
        ctx = ErrorContext(
            dataclass_name="Config",
            source=EnvSource(prefix="APP_", nested_sep="_"),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["database", "port"], ctx, file_content=None)
        assert locs[0].env_var_name == "APP_DATABASE_PORT"

    def test_json_source_with_line(self, tmp_path):
        content = '{\n  "timeout": "30",\n  "name": "test"\n}'
        config_file = tmp_path / "config.json"
        config_file.write_text(content)
        ctx = ErrorContext(
            dataclass_name="Config",
            source=JsonSource(file=config_file),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["timeout"], ctx, file_content=None)
        assert locs[0].location_label == "FILE"
        assert locs[0].line_range == LineRange(start=2, end=2)
        assert locs[0].line_content == ['"timeout": "30",']

    def test_toml_source_with_line(self, tmp_path):
        content = 'timeout = "30"\nname = "test"'
        config_file = tmp_path / "config.toml"
        config_file.write_text(content)
        ctx = ErrorContext(
            dataclass_name="Config",
            source=Toml11Source(file=config_file),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["timeout"], ctx, file_content=None)
        assert locs[0].location_label == "FILE"
        assert locs[0].line_range == LineRange(start=1, end=1)
        assert locs[0].line_content == ['timeout = "30"']

    def test_envfilesource(self, tmp_path):
        content = "# comment\nAPP_TIMEOUT=30\nAPP_NAME=test"
        env_file = tmp_path / "dummy.env"
        env_file.write_text(content)
        ctx = ErrorContext(
            dataclass_name="Config",
            source=EnvFileSource(file=env_file, prefix="APP_"),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["timeout"], ctx, file_content=None)
        assert locs[0].location_label == "ENV FILE"
        assert locs[0].env_var_name == "APP_TIMEOUT"
        assert locs[0].line_range == LineRange(start=2, end=2)
        assert locs[0].line_content == ["APP_TIMEOUT=30"]

    def test_filesource_does_not_mask_non_secret_field(self, tmp_path):
        content = '{\n  "password": "secret123",\n  "timeout": "30"\n}'
        config_file = tmp_path / "config.json"
        config_file.write_text(content)
        ctx = ErrorContext(
            dataclass_name="Config",
            source=JsonSource(file=config_file),
            secret_paths=frozenset({"password"}),
            masking=_SECRETS_ONLY,
        )
        locs = resolve_source_location(["timeout"], ctx, file_content=content)
        assert locs[0].line_content == ['"timeout": "30"']

    def test_filesource_masks_secret_field(self, tmp_path):
        content = '{\n  "password": "secret123",\n  "timeout": "30"\n}'
        config_file = tmp_path / "config.json"
        config_file.write_text(content)
        ctx = ErrorContext(
            dataclass_name="Config",
            source=JsonSource(file=config_file),
            secret_paths=frozenset({"password"}),
            masking=_SECRETS_ONLY,
        )
        locs = resolve_source_location(["password"], ctx, file_content=content)
        assert locs[0].line_content == ['"password": "<REDACTED>",']

    def test_filesource_none_mode_keeps_secret_field(self, tmp_path):
        """masking_mode="none" means no masking at all, even for a declared secret path."""
        content = '{\n  "password": "secret123",\n  "timeout": "30"\n}'
        config_file = tmp_path / "config.json"
        config_file.write_text(content)
        ctx = ErrorContext(
            dataclass_name="Config",
            source=JsonSource(file=config_file),
            secret_paths=frozenset({"password"}),
            masking=_NO_MASKING,
        )
        locs = resolve_source_location(["password"], ctx, file_content=content)
        assert locs[0].line_content == ['"password": "secret123",']

    def test_filesource_masks_line_when_secret_on_same_line(self, tmp_path):
        content = '{"password": "secret123", "timeout": "30"}'
        config_file = tmp_path / "config.json"
        config_file.write_text(content)
        ctx = ErrorContext(
            dataclass_name="Config",
            source=JsonSource(file=config_file),
            secret_paths=frozenset({"password"}),
            masking=_SECRETS_ONLY,
        )
        locs = resolve_source_location(["timeout"], ctx, file_content=content)
        assert locs[0].line_content == ['{"password": "<REDACTED>", "timeout": "30"}']

    @pytest.mark.parametrize(
        "raw_key",
        ["secret-key", "secretKey", "SECRET_KEY"],
        ids=["kebab", "lower-camel", "upper-snake"],
    )
    def test_masks_styled_secret_on_same_line(self, tmp_path, raw_key: str):
        content = f'{{"{raw_key}": "secret123", "timeout": "30"}}'
        config_file = tmp_path / "config.json"
        config_file.write_text(content)
        ctx = ErrorContext(
            dataclass_name="Config",
            source=JsonSource(file=config_file),
            secret_paths=frozenset({"secret_key"}),
            masking=_SECRETS_ONLY,
        )
        locs = resolve_source_location(["timeout"], ctx, file_content=content)
        assert locs[0].line_content == [f'{{"{raw_key}": "<REDACTED>", "timeout": "30"}}']
