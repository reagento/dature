from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import Source, load
from dature.errors import DatureConfigError, FieldLoadError, LineRange, SourceLocation


class TestDatureConfigErrorFormat:
    def test_single_error_message(self):
        errors = [
            FieldLoadError(
                field_path=["timeout"],
                message="Expected int, got str",
                input_value="30",
                locations=[
                    SourceLocation(
                        display_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=2, end=2),
                        line_content=['timeout = "30"'],
                        env_var_name=None,
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
                        display_label="FILE",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=2, end=2),
                        line_content=['"timeout": "abc"'],
                        env_var_name=None,
                    ),
                ],
            ),
            FieldLoadError(
                field_path=["db", "port"],
                message="Missing required field",
                input_value=None,
                locations=[
                    SourceLocation(
                        display_label="FILE",
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
                        display_label="ENV",
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
        # key "name" and value "name" are identical — caret should point to the value (rfind)
        errors = [
            FieldLoadError(
                field_path=["name"],
                message="Expected int, got str",
                input_value="name",
                locations=[
                    SourceLocation(
                        display_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=1, end=1),
                        line_content=['name = "name"'],
                        env_var_name=None,
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
                        display_label="FILE",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=2, end=2),
                        line_content=['"host": "host"'],
                        env_var_name=None,
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

        metadata = Source(file=json_file)

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
        content = json_file.read_text()
        caret_pos = content.rfind("abc")
        assert str(err.exceptions[0]) == (
            f"  [timeout]  invalid literal for int() with base 10: 'abc'\n"
            f"   ├── {content}\n"
            f"   │   {' ' * caret_pos}^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_json_missing_field_function(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        @dataclass
        class Config:
            name: str
            port: int

        metadata = Source(file=json_file)

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

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 2
        paths = sorted(e.field_path for e in err.exceptions if isinstance(e, FieldLoadError))
        assert paths == [["name"], ["timeout"]]
        assert str(err) == "Config loading errors (2)"
        timeout_err = next(e for e in err.exceptions if isinstance(e, FieldLoadError) and e.field_path == ["timeout"])
        name_err = next(e for e in err.exceptions if isinstance(e, FieldLoadError) and e.field_path == ["name"])
        content = json_file.read_text()
        caret_pos = content.rfind("abc")
        assert str(timeout_err) == (
            f"  [timeout]  invalid literal for int() with base 10: 'abc'\n"
            f"   ├── {content}\n"
            f"   │   {' ' * caret_pos}^^^\n"
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

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["db", "port"]
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            f"  [db.port]  invalid literal for int() with base 10: 'abc'\n"
            '   ├── "port": "abc"\n'
            "   │            ^^^\n"
            f"   └── FILE '{json_file}', line 4"
        )

    def test_env_type_error(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("APP_TIMEOUT", "abc")
        monkeypatch.setenv("APP_NAME", "test")

        metadata = Source(prefix="APP_")

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
            "  [timeout]  invalid literal for int() with base 10: 'abc'\n   └── ENV 'APP_TIMEOUT'"
        )

    def test_toml_with_line_number(self, tmp_path: Path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('name = "test"\ntimeout = "abc"\n')

        @dataclass
        class Config:
            name: str
            timeout: int

        metadata = Source(file=toml_file)

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
            f"  [timeout]  invalid literal for int() with base 10: 'abc'\n"
            '   ├── timeout = "abc"\n'
            "   │              ^^^\n"
            f"   └── FILE '{toml_file}', line 2"
        )

    def test_json_with_line_number(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{\n  "name": "test",\n  "timeout": "abc"\n}')

        @dataclass
        class Config:
            name: str
            timeout: int

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.locations
        assert first.locations[0].line_range == LineRange(start=3, end=3)
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            f"  [timeout]  invalid literal for int() with base 10: 'abc'\n"
            '   ├── "timeout": "abc"\n'
            "   │               ^^^\n"
            f"   └── FILE '{json_file}', line 3"
        )


class TestLineTruncation:
    @pytest.mark.parametrize(
        ("line_content", "expected_content"),
        [
            pytest.param(
                "a" * 80,
                "a" * 80,
                id="exactly_80_chars_not_truncated",
            ),
            pytest.param(
                "b" * 81,
                "b" * 77 + "...",
                id="81_chars_truncated",
            ),
            pytest.param(
                "c" * 120,
                "c" * 77 + "...",
                id="120_chars_truncated",
            ),
        ],
    )
    def test_filesource_truncation(
        self,
        line_content: str,
        expected_content: str,
    ) -> None:
        errors = [
            FieldLoadError(
                field_path=["timeout"],
                message="Expected int, got str",
                input_value="30",
                locations=[
                    SourceLocation(
                        display_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=2, end=2),
                        line_content=[line_content],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == "Config loading errors (1)"
        assert str(exc.exceptions[0]) == (
            f"  [timeout]  Expected int, got str\n   ├── {expected_content}\n   └── FILE 'config.toml', line 2"
        )

    @pytest.mark.parametrize(
        ("line_content", "expected_content"),
        [
            pytest.param(
                "a" * 80,
                "a" * 80,
                id="exactly_80_chars_not_truncated",
            ),
            pytest.param(
                "b" * 81,
                "b" * 77 + "...",
                id="81_chars_truncated",
            ),
            pytest.param(
                "c" * 120,
                "c" * 77 + "...",
                id="120_chars_truncated",
            ),
        ],
    )
    def test_envfilesource_truncation(
        self,
        line_content: str,
        expected_content: str,
    ) -> None:
        errors = [
            FieldLoadError(
                field_path=["timeout"],
                message="invalid literal for int() with base 10: 'abc'",
                input_value="abc",
                locations=[
                    SourceLocation(
                        display_label="ENV FILE",
                        file_path=Path(".env"),
                        line_range=LineRange(start=2, end=2),
                        line_content=[line_content],
                        env_var_name="APP_TIMEOUT",
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == "Config loading errors (1)"
        assert str(exc.exceptions[0]) == (
            f"  [timeout]  invalid literal for int() with base 10: 'abc'\n"
            f"   ├── {expected_content}\n"
            f"   └── ENV FILE '.env', line 2"
        )

    def test_multiline_content_each_line_truncated(self) -> None:
        line_short = "short line"
        line_long = "x" * 100
        errors = [
            FieldLoadError(
                field_path=["db"],
                message="Expected int, got dict",
                input_value=None,
                locations=[
                    SourceLocation(
                        display_label="FILE",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=2, end=4),
                        line_content=[line_long, line_short, line_long],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        truncated = "x" * 77 + "..."
        assert str(exc) == "Config loading errors (1)"
        assert str(exc.exceptions[0]) == (
            "  [db]  Expected int, got dict\n"
            f"   ├── {truncated}\n"
            f"   ├── {line_short}\n"
            f"   ├── {truncated}\n"
            "   └── FILE 'config.json', line 2-4"
        )

    def test_four_lines_shows_two_and_ellipsis(self) -> None:
        errors = [
            FieldLoadError(
                field_path=["db"],
                message="Expected int, got dict",
                input_value=None,
                locations=[
                    SourceLocation(
                        display_label="FILE",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=2, end=5),
                        line_content=["line1", "line2", "line3", "line4"],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == "Config loading errors (1)"
        assert str(exc.exceptions[0]) == (
            "  [db]  Expected int, got dict\n"
            "   ├── line1\n"
            "   ├── line2\n"
            "   ├── ...\n"
            "   └── FILE 'config.json', line 2-5"
        )

    def test_five_lines_shows_two_and_ellipsis(self) -> None:
        errors = [
            FieldLoadError(
                field_path=["db"],
                message="Expected int, got dict",
                input_value=None,
                locations=[
                    SourceLocation(
                        display_label="FILE",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=2, end=6),
                        line_content=["line1", "line2", "line3", "line4", "line5"],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == "Config loading errors (1)"
        assert str(exc.exceptions[0]) == (
            "  [db]  Expected int, got dict\n"
            "   ├── line1\n"
            "   ├── line2\n"
            "   ├── ...\n"
            "   └── FILE 'config.json', line 2-6"
        )


class TestCaretTruncation:
    def test_value_fully_past_truncation_skips_caret(self) -> None:
        # "port": 0 at position 85+, past max_line_length=80 truncation boundary (77 visible chars)
        line = '{"key1": "aaaaaaaaaaaaaaaaaaaaaaaaaaa", "key2": "bbbbbbbbbbbbbbbbbbbbbbbbb", "port": 0}'
        errors = [
            FieldLoadError(
                field_path=["port"],
                message="Expected str, got int",
                input_value=0,
                locations=[
                    SourceLocation(
                        display_label="FILE",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=1, end=1),
                        line_content=[line],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        truncated = line[:77] + "..."
        assert str(exc.exceptions[0]) == (
            f"  [port]  Expected str, got int\n   ├── {truncated}\n   └── FILE 'config.json', line 1"
        )

    def test_value_partially_truncated_shows_partial_caret(self) -> None:
        # Value starts within visible area but extends past truncation point
        padding = "x" * 73
        line = f"{padding}abcdefghij" + "y" * 10  # "abcdefghij" at pos 73, line > 80
        errors = [
            FieldLoadError(
                field_path=["field"],
                message="Expected int, got str",
                input_value="abcdefghij",
                locations=[
                    SourceLocation(
                        display_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=1, end=1),
                        line_content=[line],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        truncated = line[:77] + "..."
        assert str(exc.exceptions[0]) == (
            "  [field]  Expected int, got str\n"
            f"   ├── {truncated}\n"
            f"   │   {' ' * 73}^^^^\n"
            "   └── FILE 'config.toml', line 1"
        )

    def test_value_within_visible_area_shows_full_caret(self) -> None:
        line = 'timeout = "30"' + "x" * 70
        errors = [
            FieldLoadError(
                field_path=["timeout"],
                message="Expected int, got str",
                input_value="30",
                locations=[
                    SourceLocation(
                        display_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=2, end=2),
                        line_content=[line],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        truncated = line[:77] + "..."
        assert str(exc.exceptions[0]) == (
            "  [timeout]  Expected int, got str\n"
            f"   ├── {truncated}\n"
            "   │              ^^\n"
            "   └── FILE 'config.toml', line 2"
        )


class TestMultilineValueDisplay:
    def test_json_multiline_dict(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{\n  "db": {\n    "host": "localhost",\n    "port": "abc"\n  }\n}')

        @dataclass
        class Config:
            db: int

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [db]  int() argument must be a string, a bytes-like object or a real number, not 'dict'\n"
            '   ├── "db": {\n'
            '   ├──   "host": "localhost",\n'
            "   ├── ...\n"
            f"   └── FILE '{json_file}', line 2-5"
        )

    def test_yaml_multiline_block(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("db:\n  host: localhost\n  port: abc\nname: test\n")

        @dataclass
        class Config:
            db: int
            name: str

        metadata = Source(file=yaml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [db]  int() argument must be a string, a bytes-like object or a real number, not 'dict'\n"
            "   ├── db:\n"
            "   ├──   host: localhost\n"
            "   ├──   port: abc\n"
            f"   └── FILE '{yaml_file}', line 1-3"
        )

    def test_toml_multiline_array(self, tmp_path: Path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('tags = [\n  "a",\n  "b"\n]\n')

        @dataclass
        class Config:
            tags: int

        metadata = Source(file=toml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [tags]  int() argument must be a string, a bytes-like object or a real number, not 'list'\n"
            "   ├── tags = [\n"
            '   ├──   "a",\n'
            "   ├── ...\n"
            f"   └── FILE '{toml_file}', line 1-4"
        )

    def test_json_multiline_array(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{\n  "tags": [\n    "a",\n    "b"\n  ]\n}')

        @dataclass
        class Config:
            tags: int

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [tags]  int() argument must be a string, a bytes-like object or a real number, not 'list'\n"
            '   ├── "tags": [\n'
            '   ├──   "a",\n'
            "   ├── ...\n"
            f"   └── FILE '{json_file}', line 2-5"
        )

    def test_toml_array_of_tables_success(self, array_of_tables_toml_file: Path):
        @dataclass
        class Product:
            name: str
            sku: int

        @dataclass
        class Config:
            product: list[Product]

        metadata = Source(file=array_of_tables_toml_file)
        result = load(metadata, schema=Config)

        assert result == Config(
            product=[
                Product(name="Hammer", sku=738594937),
                Product(name="Nail", sku=284758393),
            ],
        )

    def test_toml_array_of_tables_error(self, array_of_tables_error_first_toml_file: Path):

        @dataclass
        class Product:
            name: str
            sku: int

        @dataclass
        class Config:
            product: list[Product]

        metadata = Source(file=array_of_tables_error_first_toml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [product.0.sku]  invalid literal for int() with base 10: 'not_a_number'\n"
            '   ├── sku = "not_a_number"\n'
            "   │          ^^^^^^^^^^^^\n"
            f"   └── FILE '{array_of_tables_error_first_toml_file}', line 3"
        )

    def test_toml_array_of_tables_error_last_element(self, array_of_tables_error_last_toml_file: Path):
        @dataclass
        class Product:
            name: str
            sku: int

        @dataclass
        class Config:
            product: list[Product]

        metadata = Source(file=array_of_tables_error_last_toml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [product.1.sku]  invalid literal for int() with base 10: 'not_a_number'\n"
            '   ├── sku = "not_a_number"\n'
            "   │          ^^^^^^^^^^^^\n"
            f"   └── FILE '{array_of_tables_error_last_toml_file}', line 7"
        )
