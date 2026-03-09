from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError, FieldLoadError, LineRange, SourceLocation


class TestDatureConfigErrorFormat:
    def test_single_error_message(self):
        errors = [
            FieldLoadError(
                field_path=["timeout"],
                message="Expected int, got str",
                input_value="30",
                locations=[
                    SourceLocation(
                        source_type="toml",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=2, end=2),
                        line_content=['timeout = "30"'],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == dedent("""\
            Config loading errors (1)

              [timeout]  Expected int, got str
               └── FILE 'config.toml', line 2
                   timeout = "30"
            """)

    def test_multiple_errors_message(self):
        errors = [
            FieldLoadError(
                field_path=["timeout"],
                message="Bad string format",
                input_value="abc",
                locations=[
                    SourceLocation(
                        source_type="json",
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
                        source_type="json",
                        file_path=Path("config.json"),
                        line_range=None,
                        line_content=None,
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == dedent("""\
            Config loading errors (2)

              [timeout]  Bad string format
               └── FILE 'config.json', line 2
                   "timeout": "abc"

              [db.port]  Missing required field
               └── FILE 'config.json'
            """)

    def test_env_error_message(self):
        errors = [
            FieldLoadError(
                field_path=["database", "port"],
                message="Bad string format",
                input_value="abc",
                locations=[
                    SourceLocation(
                        source_type="env",
                        file_path=None,
                        line_range=None,
                        line_content=None,
                        env_var_name="APP_DATABASE__PORT",
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == dedent("""\
            Config loading errors (1)

              [database.port]  Bad string format
               └── ENV 'APP_DATABASE__PORT'
            """)


class TestLoadIntegrationErrors:
    def test_json_type_error_decorator(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"timeout": "abc", "name": "test"}')

        metadata = LoadMetadata(file_=json_file)

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
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [timeout]  Bad string format
               └── FILE '{json_file}', line 1
                   {json_file.read_text()}
            """)

    def test_json_missing_field_function(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        @dataclass
        class Config:
            name: str
            port: int

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["port"]
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [port]  Missing required field
               └── FILE '{json_file}'
            """)

    def test_multiple_errors_at_once(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"timeout": "abc"}')

        @dataclass
        class Config:
            timeout: int
            name: str

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert len(err.exceptions) == 2
        paths = sorted(e.field_path for e in err.exceptions if isinstance(e, FieldLoadError))
        assert paths == [["name"], ["timeout"]]
        assert str(err) == dedent(f"""\
            Config loading errors (2)

              [timeout]  Bad string format
               └── FILE '{json_file}', line 1
                   {json_file.read_text()}

              [name]  Missing required field
               └── FILE '{json_file}'
            """)

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

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.field_path == ["db", "port"]
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [db.port]  Bad string format
               └── FILE '{json_file}', line 4
                   "port": "abc"
            """)

    def test_env_type_error(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("APP_TIMEOUT", "abc")
        monkeypatch.setenv("APP_NAME", "test")

        metadata = LoadMetadata(prefix="APP_")

        @load(metadata)
        @dataclass
        class Config:
            timeout: int
            name: str

        with pytest.raises(DatureConfigError) as exc_info:
            Config()

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == dedent("""\
            Config loading errors (1)

              [timeout]  Bad string format
               └── ENV 'APP_TIMEOUT'
            """)

    def test_toml_with_line_number(self, tmp_path: Path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('name = "test"\ntimeout = "abc"\n')

        @dataclass
        class Config:
            name: str
            timeout: int

        metadata = LoadMetadata(file_=toml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.locations
        assert first.locations[0].line_range == LineRange(start=2, end=2)
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [timeout]  Bad string format
               └── FILE '{toml_file}', line 2
                   timeout = "abc"
            """)

    def test_json_with_line_number(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{\n  "name": "test",\n  "timeout": "abc"\n}')

        @dataclass
        class Config:
            name: str
            timeout: int

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert first.locations
        assert first.locations[0].line_range == LineRange(start=3, end=3)
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [timeout]  Bad string format
               └── FILE '{json_file}', line 3
                   "timeout": "abc"
            """)


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
    def test_file_source_truncation(
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
                        source_type="toml",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=2, end=2),
                        line_content=[line_content],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == dedent(f"""\
            Config loading errors (1)

              [timeout]  Expected int, got str
               └── FILE 'config.toml', line 2
                   {expected_content}
            """)

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
    def test_envfile_source_truncation(
        self,
        line_content: str,
        expected_content: str,
    ) -> None:
        errors = [
            FieldLoadError(
                field_path=["timeout"],
                message="Bad string format",
                input_value="abc",
                locations=[
                    SourceLocation(
                        source_type="envfile",
                        file_path=Path(".env"),
                        line_range=LineRange(start=2, end=2),
                        line_content=[line_content],
                        env_var_name="APP_TIMEOUT",
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == dedent(f"""\
            Config loading errors (1)

              [timeout]  Bad string format
               └── ENV FILE '.env', line 2
                   {expected_content}
            """)

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
                        source_type="json",
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
        assert str(exc) == dedent(f"""\
            Config loading errors (1)

              [db]  Expected int, got dict
               └── FILE 'config.json', line 2-4
                   {truncated}
                   {line_short}
                   {truncated}
            """)

    def test_four_lines_shows_two_and_ellipsis(self) -> None:
        errors = [
            FieldLoadError(
                field_path=["db"],
                message="Expected int, got dict",
                input_value=None,
                locations=[
                    SourceLocation(
                        source_type="json",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=2, end=5),
                        line_content=["line1", "line2", "line3", "line4"],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == dedent("""\
            Config loading errors (1)

              [db]  Expected int, got dict
               └── FILE 'config.json', line 2-5
                   line1
                   line2
                   ...
            """)

    def test_five_lines_shows_two_and_ellipsis(self) -> None:
        errors = [
            FieldLoadError(
                field_path=["db"],
                message="Expected int, got dict",
                input_value=None,
                locations=[
                    SourceLocation(
                        source_type="json",
                        file_path=Path("config.json"),
                        line_range=LineRange(start=2, end=6),
                        line_content=["line1", "line2", "line3", "line4", "line5"],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc) == dedent("""\
            Config loading errors (1)

              [db]  Expected int, got dict
               └── FILE 'config.json', line 2-6
                   line1
                   line2
                   ...
            """)


class TestMultilineValueDisplay:
    def test_json_multiline_dict(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{\n  "db": {\n    "host": "localhost",\n    "port": "abc"\n  }\n}')

        @dataclass
        class Config:
            db: int

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [db]  Expected int | float | str, got dict
               └── FILE '{json_file}', line 2-5
                   "db": {{
                     "host": "localhost",
                   ...
            """)

    def test_yaml_multiline_block(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("db:\n  host: localhost\n  port: abc\nname: test\n")

        @dataclass
        class Config:
            db: int
            name: str

        metadata = LoadMetadata(file_=yaml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [db]  Expected int | float | str, got dict
               └── FILE '{yaml_file}', line 1-3
                   db:
                     host: localhost
                     port: abc
            """)

    def test_toml_multiline_array(self, tmp_path: Path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('tags = [\n  "a",\n  "b"\n]\n')

        @dataclass
        class Config:
            tags: int

        metadata = LoadMetadata(file_=toml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [tags]  Expected int | float | str, got list
               └── FILE '{toml_file}', line 1-4
                   tags = [
                     "a",
                   ...
            """)

    def test_json_multiline_array(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{\n  "tags": [\n    "a",\n    "b"\n  ]\n}')

        @dataclass
        class Config:
            tags: int

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [tags]  Expected int | float | str, got list
               └── FILE '{json_file}', line 2-5
                   "tags": [
                     "a",
                   ...
            """)

    def test_toml_array_of_tables_success(self, array_of_tables_toml_file: Path):
        @dataclass
        class Product:
            name: str
            sku: int

        @dataclass
        class Config:
            product: list[Product]

        metadata = LoadMetadata(file_=array_of_tables_toml_file)
        result = load(metadata, Config)

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

        metadata = LoadMetadata(file_=array_of_tables_error_first_toml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [product.0.sku]  Bad string format
               └── FILE '{array_of_tables_error_first_toml_file}', line 3
                   sku = "not_a_number"
            """)

    def test_toml_array_of_tables_error_last_element(self, array_of_tables_error_last_toml_file: Path):
        @dataclass
        class Product:
            name: str
            sku: int

        @dataclass
        class Config:
            product: list[Product]

        metadata = LoadMetadata(file_=array_of_tables_error_last_toml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == dedent(f"""\
            Config loading errors (1)

              [product.1.sku]  Bad string format
               └── FILE '{array_of_tables_error_last_toml_file}', line 7
                   sku = "not_a_number"
            """)
