"""Tests for loading/multi.py — multi-source config loading."""

from dataclasses import dataclass
from enum import Flag
from pathlib import Path
from textwrap import dedent
from typing import Annotated

import pytest

from dature import Source, load
from dature.errors import DatureConfigError, MergeConflictError
from dature.validators.number import Ge


class TestMergeLoadAsFunction:
    def test_two_json_sources_last_wins(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            schema=Config,
        )

        assert result.host == "localhost"
        assert result.port == 8080

    def test_two_json_sources_first_wins(self, tmp_path: Path):
        first = tmp_path / "first.json"
        first.write_text('{"host": "first-host", "port": 3000}')

        second = tmp_path / "second.json"
        second.write_text('{"host": "second-host", "port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=first),
            Source(file=second),
            schema=Config,
            strategy="first_wins",
        )

        assert result.host == "first-host"
        assert result.port == 3000

    def test_partial_sources(self, tmp_path: Path):
        filea = tmp_path / "a.json"
        filea.write_text('{"host": "myhost"}')

        fileb = tmp_path / "b.json"
        fileb.write_text('{"port": 9090}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=filea),
            Source(file=fileb),
            schema=Config,
        )

        assert result.host == "myhost"
        assert result.port == 9090

    def test_nested_dataclass(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"database": {"host": "localhost", "port": 5432}}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"database": {"host": "prod-host"}}')

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            schema=Config,
        )

        assert result.database.host == "prod-host"
        assert result.database.port == 5432

    def test_three_sources(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "a-host", "port": 1000, "debug": false}')

        b = tmp_path / "b.json"
        b.write_text('{"port": 2000}')

        c = tmp_path / "c.json"
        c.write_text('{"debug": true}')

        @dataclass
        class Config:
            host: str
            port: int
            debug: bool

        result = load(
            Source(file=a),
            Source(file=b),
            Source(file=c),
            schema=Config,
        )

        assert result.host == "a-host"
        assert result.port == 2000
        assert result.debug is True

    def test_tuple_shorthand(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            schema=Config,
        )

        assert result.host == "localhost"
        assert result.port == 8080

    def test_json_and_env(self, tmp_path: Path, monkeypatch):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        monkeypatch.setenv("APP_PORT", "9090")
        monkeypatch.setenv("APP_HOST", "env-host")

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=defaults),
            Source(prefix="APP_"),
            schema=Config,
        )

        assert result.host == "env-host"
        assert result.port == 9090

    def test_json_and_env_missing_field_error(self, tmp_path: Path, monkeypatch):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost"}')

        monkeypatch.delenv("APP_PORT", raising=False)
        monkeypatch.delenv("APP_HOST", raising=False)

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=defaults),
                Source(prefix="APP_"),
                schema=Config,
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == ("  [port]  Missing required field\n   └── ENV 'APP_PORT'")

    def test_missing_field_in_all_sources(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "localhost"}')

        b = tmp_path / "b.json"
        b.write_text("{}")

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=a),
                Source(file=b),
                schema=Config,
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (f"  [port]  Missing required field\n   └── FILE '{b}'")

    def test_backward_compat_single_load_metadata(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        result = load(Source(file=json_file), schema=Config)

        assert result.name == "test"
        assert result.port == 8080

    def test_backward_compat_none_metadata(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "from_env")

        @dataclass
        class Config:
            my_var: str

        result = load(Source(), schema=Config)

        assert result.my_var == "from_env"


class TestMergeAsDecorator:
    def test_decorator_with_merge(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 9090}')

        @load(
            Source(file=defaults),
            Source(file=overrides),
        )
        @dataclass
        class Config:
            host: str
            port: int

        config = Config()
        assert config.host == "localhost"
        assert config.port == 9090

    def test_decorator_cache(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "original", "port": 3000}')

        @load(Source(file=defaults))
        @dataclass
        class Config:
            host: str
            port: int

        first = Config()
        defaults.write_text('{"host": "updated", "port": 9090}')
        second = Config()

        assert first.host == "original"
        assert second.host == "original"

    def test_decorator_no_cache(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "original", "port": 3000}')

        @load(Source(file=defaults), cache=False)
        @dataclass
        class Config:
            host: str
            port: int

        first = Config()
        defaults.write_text('{"host": "updated", "port": 9090}')
        second = Config()

        assert first.host == "original"
        assert second.host == "updated"

    def test_decorator_with_tuple(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        @load(
            Source(file=defaults),
            Source(file=overrides),
        )
        @dataclass
        class Config:
            host: str
            port: int

        config = Config()
        assert config.host == "localhost"
        assert config.port == 8080

    def test_decorator_init_override(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        @load(Source(file=defaults))
        @dataclass
        class Config:
            host: str
            port: int

        config = Config(host="overridden")
        assert config.host == "overridden"
        assert config.port == 3000

    def test_decorator_not_dataclass(self):
        with pytest.raises(TypeError, match="must be a dataclass"):

            @load(Source())
            class NotDataclass:
                pass

    def test_decorator_first_wins(self, tmp_path: Path):
        first = tmp_path / "first.json"
        first.write_text('{"host": "first-host", "port": 1000}')

        second = tmp_path / "second.json"
        second.write_text('{"host": "second-host", "port": 2000}')

        @load(
            Source(file=first),
            Source(file=second),
            strategy="first_wins",
        )
        @dataclass
        class Config:
            host: str
            port: int

        config = Config()
        assert config.host == "first-host"
        assert config.port == 1000


class TestRaiseOnConflict:
    def test_raises_on_scalar_conflict(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{\n  "host": "host-a",\n  "port": 3000\n}')

        b = tmp_path / "b.json"
        b.write_text('{\n  "host": "host-b"\n}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(MergeConflictError) as exc_info:
            load(
                Source(file=a),
                Source(file=b),
                schema=Config,
                strategy="raise_on_conflict",
            )

        assert str(exc_info.value) == dedent(f"""\
            Config merge conflicts (1)

              [host]  Conflicting values in multiple sources
               ├── "host": "host-a",
               └── FILE '{a}', line 2
               ├── "host": "host-b"
               └── FILE '{b}', line 2
            """)

    def test_no_conflict_disjoint_keys(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "localhost"}')

        b = tmp_path / "b.json"
        b.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=a),
            Source(file=b),
            schema=Config,
            strategy="raise_on_conflict",
        )

        assert result.host == "localhost"
        assert result.port == 8080

    def test_no_conflict_same_values(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "same", "port": 3000}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "same", "port": 3000}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=a),
            Source(file=b),
            schema=Config,
            strategy="raise_on_conflict",
        )

        assert result.host == "same"
        assert result.port == 3000

    def test_nested_conflict(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{\n  "database": {\n    "host": "a-host",\n    "port": 5432\n  }\n}')

        b = tmp_path / "b.json"
        b.write_text('{\n  "database": {\n    "host": "b-host"\n  }\n}')

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database

        with pytest.raises(MergeConflictError) as exc_info:
            load(
                Source(file=a),
                Source(file=b),
                schema=Config,
                strategy="raise_on_conflict",
            )

        assert str(exc_info.value) == dedent(f"""\
            Config merge conflicts (1)

              [database.host]  Conflicting values in multiple sources
               ├── "host": "a-host",
               └── FILE '{a}', line 3
               ├── "host": "b-host"
               └── FILE '{b}', line 3
            """)

    def test_conflict_error_message_format(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{\n  "host": "a-host"\n}')

        b = tmp_path / "b.json"
        b.write_text('{\n  "host": "b-host"\n}')

        @dataclass
        class Config:
            host: str

        with pytest.raises(MergeConflictError) as exc_info:
            load(
                Source(file=a),
                Source(file=b),
                schema=Config,
                strategy="raise_on_conflict",
            )

        assert str(exc_info.value) == dedent(f"""\
            Config merge conflicts (1)

              [host]  Conflicting values in multiple sources
               ├── "host": "a-host"
               └── FILE '{a}', line 2
               ├── "host": "b-host"
               └── FILE '{b}', line 2
            """)

    def test_conflict_with_env_source(self, tmp_path: Path, monkeypatch):
        a = tmp_path / "a.json"
        a.write_text('{\n  "host": "json-host",\n  "port": 3000\n}')

        monkeypatch.setenv("APP_HOST", "env-host")

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(MergeConflictError) as exc_info:
            load(
                Source(file=a),
                Source(prefix="APP_"),
                schema=Config,
                strategy="raise_on_conflict",
            )

        assert str(exc_info.value) == dedent(f"""\
            Config merge conflicts (1)

              [host]  Conflicting values in multiple sources
               ├── "host": "json-host",
               └── FILE '{a}', line 2
               └── ENV 'APP_HOST'
            """)

    def test_multiple_conflicts(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{\n  "host": "a-host",\n  "port": 1000\n}')

        b = tmp_path / "b.json"
        b.write_text('{\n  "host": "b-host",\n  "port": 2000\n}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(MergeConflictError) as exc_info:
            load(
                Source(file=a),
                Source(file=b),
                schema=Config,
                strategy="raise_on_conflict",
            )

        assert len(exc_info.value.exceptions) == 2
        assert str(exc_info.value) == dedent(f"""\
            Config merge conflicts (2)

              [host]  Conflicting values in multiple sources
               ├── "host": "a-host",
               └── FILE '{a}', line 2
               ├── "host": "b-host",
               └── FILE '{b}', line 2

              [port]  Conflicting values in multiple sources
               ├── "port": 1000
               └── FILE '{a}', line 3
               ├── "port": 2000
               └── FILE '{b}', line 3
            """)

    def test_is_subclass_of_dature_config_error(self):
        assert issubclass(MergeConflictError, DatureConfigError)


class TestMergeWithYamlAndEnvFile:
    def test_yaml_and_env_file(self, tmp_path: Path):
        yaml_file = tmp_path / "defaults.yaml"
        yaml_file.write_text("host: localhost\nport: 3000\n")

        env_file = tmp_path / "overrides.env"
        env_file.write_text("PORT=9090\n")

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=yaml_file),
            Source(file=env_file),
            schema=Config,
        )

        assert result.host == "localhost"
        assert result.port == 9090


class _Permission(Flag):
    READ = 1
    WRITE = 2
    EXECUTE = 4


class TestCoerceFlagFieldsMergeMode:
    def test_flag_from_env_filemerge(self, tmp_path: Path):
        json_file = tmp_path / "defaults.json"
        json_file.write_text('{"name": "app"}')

        env_file = tmp_path / "overrides.env"
        env_file.write_text("PERMS=3\n")

        @dataclass
        class Config:
            name: str
            perms: _Permission

        result = load(
            Source(file=json_file),
            Source(file=env_file),
            schema=Config,
        )

        assert result.perms == _Permission.READ | _Permission.WRITE

    def test_flag_from_env_vars_merge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        json_file = tmp_path / "defaults.json"
        json_file.write_text('{"name": "app"}')

        monkeypatch.setenv("APP_PERMS", "5")

        @dataclass
        class Config:
            name: str
            perms: _Permission

        result = load(
            Source(file=json_file),
            Source(prefix="APP_"),
            schema=Config,
        )

        assert result.perms == _Permission.READ | _Permission.EXECUTE

    def test_flag_from_json_merge_as_int(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"name": "app"}')

        b = tmp_path / "b.json"
        b.write_text('{"perms": 7}')

        @dataclass
        class Config:
            name: str
            perms: _Permission

        result = load(
            Source(file=a),
            Source(file=b),
            schema=Config,
        )

        assert result.perms == _Permission.READ | _Permission.WRITE | _Permission.EXECUTE

    def test_flag_decorator_merge_from_env_file(self, tmp_path: Path):
        json_file = tmp_path / "defaults.json"
        json_file.write_text('{"name": "app"}')

        env_file = tmp_path / "overrides.env"
        env_file.write_text("PERMS=6\n")

        @dataclass
        class Config:
            name: str
            perms: _Permission

        @load(
            Source(file=json_file),
            Source(file=env_file),
        )
        @dataclass
        class MergedConfig:
            name: str
            perms: _Permission

        config = MergedConfig()
        assert config.perms == _Permission.WRITE | _Permission.EXECUTE


class TestFirstFound:
    def test_uses_first_source(self, tmp_path: Path):
        first = tmp_path / "first.yaml"
        first.write_text("host: first-host\nport: 1000\n")

        second = tmp_path / "second.yaml"
        second.write_text("host: second-host\nport: 2000\n")

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=first),
            Source(file=second),
            schema=Config,
            strategy="first_found",
        )

        assert result.host == "first-host"
        assert result.port == 1000

    def test_skips_missing_file(self, tmp_path: Path):
        missing = tmp_path / "missing.yaml"
        fallback = tmp_path / "fallback.yaml"
        fallback.write_text("host: fallback-host\nport: 3000\n")

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=missing),
            Source(file=fallback),
            schema=Config,
            strategy="first_found",
        )

        assert result.host == "fallback-host"
        assert result.port == 3000

    def test_skips_broken_file(self, tmp_path: Path):
        broken = tmp_path / "broken.yaml"
        broken.write_text(": invalid: yaml: [")

        fallback = tmp_path / "fallback.yaml"
        fallback.write_text("host: fallback-host\nport: 4000\n")

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=broken),
            Source(file=fallback),
            schema=Config,
            strategy="first_found",
        )

        assert result.host == "fallback-host"
        assert result.port == 4000

    def test_all_broken_raises(self, tmp_path: Path):
        missing1 = tmp_path / "missing1.yaml"
        missing2 = tmp_path / "missing2.yaml"

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=missing1),
                Source(file=missing2),
                schema=Config,
                strategy="first_found",
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == "All 2 source(s) failed to load"

    def test_does_not_merge(self, tmp_path: Path):
        partial = tmp_path / "partial.yaml"
        partial.write_text("host: partial-host\n")

        full = tmp_path / "full.yaml"
        full.write_text("host: full-host\nport: 5000\n")

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=partial),
                Source(file=full),
                schema=Config,
                strategy="first_found",
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (f"  [port]  Missing required field\n   └── FILE '{partial}'")

    def test_type_error_not_skipped(self, tmp_path: Path):
        bad_type = tmp_path / "bad_type.yaml"
        bad_type.write_text("host: valid-host\nport: not_a_number\n")

        fallback = tmp_path / "fallback.yaml"
        fallback.write_text("host: fallback-host\nport: 6000\n")

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=bad_type),
                Source(file=fallback),
                schema=Config,
                strategy="first_found",
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            f"  [port]  invalid literal for int() with base 10: 'not_a_number'\n"
            f"   ├── port: not_a_number\n"
            f"   │         ^^^^^^^^^^^^\n"
            f"   └── FILE '{bad_type}', line 2"
        )

    def test_validation_error_references_correct_source(self, tmp_path: Path):
        first = tmp_path / "first.yaml"
        first.write_text("host: first-host\nport: 0\n")

        second = tmp_path / "second.yaml"
        second.write_text("host: second-host\nport: 5000\n")

        @dataclass
        class Config:
            host: str
            port: Annotated[int, Ge(1)]

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=first),
                Source(file=second),
                schema=Config,
                strategy="first_found",
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            f"  [port]  Value must be greater than or equal to 1\n"
            f"   ├── port: 0\n"
            f"   │         ^\n"
            f"   └── FILE '{first}', line 2"
        )

    def test_validation_error_references_correct_source_decorator(self, tmp_path: Path):
        first = tmp_path / "first.yaml"
        first.write_text("host: first-host\nport: 0\n")

        second = tmp_path / "second.yaml"
        second.write_text("host: second-host\nport: 5000\n")

        @load(
            Source(file=first),
            Source(file=second),
            strategy="first_found",
            cache=False,
        )
        @dataclass
        class Config:
            host: str
            port: Annotated[int, Ge(1)]

        with pytest.raises(DatureConfigError) as exc_info:
            Config()

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            f"  [port]  Value must be greater than or equal to 1\n"
            f"   ├── port: 0\n"
            f"   │         ^\n"
            f"   └── FILE '{first}', line 2"
        )
