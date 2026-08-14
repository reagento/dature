from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import EnvSource, JsonSource, Toml11Source, load
from dature.errors import CaretSpan, DatureConfigError, FieldLoadError, LineRange, SourceLocation


class TestDatureConfigErrorFormat:
    def test_single_error_message(self):
        errors = [
            FieldLoadError(
                field_path=["timeout"],
                message="Expected int, got str",
                input_value="30",
                locations=[
                    SourceLocation(
                        location_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=2, end=2),
                        line_content=['timeout = "30"'],
                        env_var_name=None,
                        line_carets=[CaretSpan(start=11, end=13)],  # "30" at cols 11-13 in 'timeout = "30"'
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == "Config loading errors (1)"
        assert str(exc.exceptions[0]) == (
            "  [timeout]  Expected int, got str\n"
            '   ├── timeout = "30"\n'
            "   │              ^^\n"
            "   └── FILE 'config.toml', line 2"
        )

    def test_multiple_errors_message(self):
        errors = [
            FieldLoadError(
                field_path=["timeout"],
                message="invalid literal for int() with base 10: 'abc'",
                input_value="abc",
                locations=[
                    SourceLocation(
                        location_label="FILE",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=2, end=2),
                        line_content=['"timeout": "abc"'],
                        env_var_name=None,
                        line_carets=[CaretSpan(start=12, end=15)],  # "abc" at cols 12-15 in '"timeout": "abc"'
                    ),
                ],
            ),
            FieldLoadError(
                field_path=["db", "port"],
                message="Missing required field",
                input_value=None,
                locations=[
                    SourceLocation(
                        location_label="FILE",
                        file_path=Path("config.json"),
                        line_range=None,
                        line_content=None,
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == "Config loading errors (2)"
        assert str(exc.exceptions[0]) == (
            "  [timeout]  invalid literal for int() with base 10: 'abc'\n"
            '   ├── "timeout": "abc"\n'
            "   │               ^^^\n"
            "   └── FILE 'config.json', line 2"
        )
        assert str(exc.exceptions[1]) == ("  [db.port]  Missing required field\n   └── FILE 'config.json'")

    def test_env_error_message(self):
        errors = [
            FieldLoadError(
                field_path=["database", "port"],
                message="invalid literal for int() with base 10: 'abc'",
                input_value="abc",
                locations=[
                    SourceLocation(
                        location_label="ENV",
                        file_path=None,
                        line_range=None,
                        line_content=None,
                        env_var_name="APP_DATABASE__PORT",
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == "Config loading errors (1)"
        assert str(exc.exceptions[0]) == (
            "  [database.port]  invalid literal for int() with base 10: 'abc'\n   └── ENV 'APP_DATABASE__PORT'"
        )


class TestCaretPointsToValue:
    def test_caret_points_to_value_not_key_when_same_string(self) -> None:
        # key "name" and value "name" are identical — caret should point to the value (rfind pos 8)
        errors = [
            FieldLoadError(
                field_path=["name"],
                message="Expected int, got str",
                input_value="name",
                locations=[
                    SourceLocation(
                        location_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=1, end=1),
                        line_content=['name = "name"'],
                        env_var_name=None,
                        line_carets=[CaretSpan(start=8, end=12)],  # "name" at cols 8-12 in 'name = "name"'
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc.exceptions[0]) == (
            "  [name]  Expected int, got str\n"
            '   ├── name = "name"\n'
            "   │           ^^^^\n"
            "   └── FILE 'config.toml', line 1"
        )

    def test_caret_points_to_value_in_json_duplicate_string(self) -> None:
        errors = [
            FieldLoadError(
                field_path=["host"],
                message="Expected int, got str",
                input_value="host",
                locations=[
                    SourceLocation(
                        location_label="FILE",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=2, end=2),
                        line_content=['"host": "host"'],
                        env_var_name=None,
                        line_carets=[CaretSpan(start=9, end=13)],  # "host" at cols 9-13 in '"host": "host"'
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc.exceptions[0]) == (
            "  [host]  Expected int, got str\n"
            '   ├── "host": "host"\n'
            "   │            ^^^^\n"
            "   └── FILE 'config.json', line 2"
        )


class TestLoadIntegrationErrors:
    def test_json_type_error_decorator(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"timeout": "abc", "name": "test"}')

        metadata = JsonSource(file=json_file)

        @load(metadata)
        @dataclass
        class Config:
            timeout: int
            name: str

        with pytest.raises(DatureConfigError) as exc_info:
            Config()

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["timeout"]
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [timeout]  invalid literal for int() with base 10: '<REDACTED>'\n"
            '   ├── {"timeout": "<REDACTED>", "name": "<REDACTED>"}\n'
            "   │                ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_json_missing_field_function(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        @dataclass
        class Config:
            name: str
            port: int

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["port"]
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (f"  [port]  Missing required field\n   └── FILE '{json_file}'")

    def test_multiple_errors_at_once(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"timeout": "abc"}')

        @dataclass
        class Config:
            timeout: int
            name: str

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 2
        paths = sorted(e.field_path for e in err.exceptions if isinstance(e, FieldLoadError))
        assert paths == [["name"], ["timeout"]]
        assert str(err) == "Config loading errors (2)"
        timeout_err = next(e for e in err.exceptions if isinstance(e, FieldLoadError) and e.field_path == ["timeout"])
        name_err = next(e for e in err.exceptions if isinstance(e, FieldLoadError) and e.field_path == ["name"])
        assert str(timeout_err) == (
            "  [timeout]  invalid literal for int() with base 10: '<REDACTED>'\n"
            '   ├── {"timeout": "<REDACTED>"}\n'
            "   │                ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(name_err) == (f"  [name]  Missing required field\n   └── FILE '{json_file}'")

    def test_nested_dataclass_error(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{\n  "db": {\n    "host": "localhost",\n    "port": "abc"\n  }\n}')

        @dataclass
        class DB:
            host: str
            port: int

        @dataclass
        class Config:
            db: DB

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["db", "port"]
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [db.port]  invalid literal for int() with base 10: '<REDACTED>'\n"
            '   ├── "port": "<REDACTED>"\n'
            "   │            ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 4"
        )

    def test_env_type_error(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("APP_TIMEOUT", "abc")
        monkeypatch.setenv("APP_NAME", "test")

        metadata = EnvSource(prefix="APP_")

        @load(metadata)
        @dataclass
        class Config:
            timeout: int
            name: str

        with pytest.raises(DatureConfigError) as exc_info:
            Config()

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [timeout]  invalid literal for int() with base 10: '<REDACTED>'\n"
            "   ├── APP_TIMEOUT=<REDACTED>\n"
            "   │               ^^^^^^^^^^\n"
            "   └── ENV 'APP_TIMEOUT'"
        )

    def test_toml_with_line_number(self, tmp_path: Path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('name = "test"\ntimeout = "abc"\n')

        @dataclass
        class Config:
            name: str
            timeout: int

        metadata = Toml11Source(file=toml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.locations
        assert first.locations[0].line_range == LineRange(start=2, end=2)
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [timeout]  invalid literal for int() with base 10: '<REDACTED>'\n"
            '   ├── timeout = "<REDACTED>"\n'
            "   │              ^^^^^^^^^^\n"
            f"   └── FILE '{toml_file}', line 2"
        )

    def test_json_with_line_number(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{\n  "name": "test",\n  "timeout": "abc"\n}')

        @dataclass
        class Config:
            name: str
            timeout: int

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.locations
        assert first.locations[0].line_range == LineRange(start=3, end=3)
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [timeout]  invalid literal for int() with base 10: '<REDACTED>'\n"
            '   ├── "timeout": "<REDACTED>"\n'
            "   │               ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 3"
        )
