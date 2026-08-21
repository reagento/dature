from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import JsonSource, Toml11Source, Yaml12Source, configure, load
from dature.config import ErrorDisplayConfig
from dature.errors import CaretSpan, DatureConfigError, FieldLoadError, LineRange, MergeConflictError, SourceLocation
from dature.instance import Dature


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
                        location_label="FILE",
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
                        location_label="ENV FILE",
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
                        location_label="FILE",
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
                        location_label="FILE",
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
                        location_label="FILE",
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
                        location_label="FILE",
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
                        location_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=1, end=1),
                        line_content=[line],
                        env_var_name=None,
                        line_carets=[CaretSpan(start=73, end=83)],  # "abcdefghij" at cols 73-83 (truncated to 4)
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
                        location_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=2, end=2),
                        line_content=[line],
                        env_var_name=None,
                        line_carets=[CaretSpan(start=11, end=13)],  # "30" at cols 11-13 in 'timeout = "30"...'
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

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [db]  int() argument must be a string, a bytes-like object or a real number, not 'dict'\n"
            '   ├── "db": {\n'
            "   │         ^\n"
            '   ├──   "host": "<REDACTED>",\n'
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

        metadata = Yaml12Source(file=yaml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [db]  int() argument must be a string, a bytes-like object or a real number, not 'dict'\n"
            "   ├── db:\n"
            "   │   ^^^\n"
            "   ├──   host: <REDACTED>\n"
            "   ├──   port: <REDACTED>\n"
            f"   └── FILE '{yaml_file}', line 1-3"
        )

    def test_toml_multiline_array(self, tmp_path: Path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('tags = [\n  "a",\n  "b"\n]\n')

        @dataclass
        class Config:
            tags: int

        metadata = Toml11Source(file=toml_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [tags]  int() argument must be a string, a bytes-like object or a real number, not 'list'\n"
            "   ├── tags = [\n"
            "   │          ^\n"
            "   ├── <REDACTED>\n"
            "   ├── ...\n"
            f"   └── FILE '{toml_file}', line 1-4"
        )

    def test_json_multiline_array(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{\n  "tags": [\n    "a",\n    "b"\n  ]\n}')

        @dataclass
        class Config:
            tags: int

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        err = exc_info.value
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            "  [tags]  int() argument must be a string, a bytes-like object or a real number, not 'list'\n"
            '   ├── "tags": [\n'
            "   │           ^\n"
            "   ├── <REDACTED>\n"
            "   ├── ...\n"
            f"   └── FILE '{json_file}', line 2-5"
        )

    def test_multiline_caret_underlines_each_visible_line(self, tmp_path: Path):
        yaml_file = tmp_path / "c.yaml"
        yaml_file.write_text("db:\n  host: x\n  port: y\nother: z\n")

        @dataclass
        class Config:
            db: int
            other: str

        with pytest.raises(DatureConfigError) as exc_info:
            load(Yaml12Source(file=yaml_file), schema=Config)

        err = exc_info.value
        assert str(err.exceptions[0]) == (
            "  [db]  int() argument must be a string, a bytes-like object or a real number, not 'dict'\n"
            "   ├── db:\n"
            "   │   ^^^\n"
            "   ├──   host: <REDACTED>\n"
            "   ├──   port: <REDACTED>\n"
            f"   └── FILE '{yaml_file}', line 1-3"
        )

    def test_toml_array_of_tables_success(self, array_of_tables_toml_file: Path):
        @dataclass
        class Product:
            name: str
            sku: int

        @dataclass
        class Config:
            product: list[Product]

        metadata = Toml11Source(file=array_of_tables_toml_file)
        result = load(metadata, schema=Config)

        assert result == Config(
            product=[
                Product(name="Hammer", sku=738594937),
                Product(name="Nail", sku=284758393),
            ],
        )

    @pytest.mark.usefixtures("_reset_config")
    def test_toml_array_of_tables_error(self, array_of_tables_error_first_toml_file: Path):
        # This test isn't about masking — disable it so the rendered error message
        # shows the literal invalid value (the default mode masks every string).
        configure(masking={"masking_mode": "none"})

        @dataclass
        class Product:
            name: str
            sku: int

        @dataclass
        class Config:
            product: list[Product]

        metadata = Toml11Source(file=array_of_tables_error_first_toml_file)

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

    @pytest.mark.usefixtures("_reset_config")
    def test_toml_array_of_tables_error_last_element(self, array_of_tables_error_last_toml_file: Path):
        # This test isn't about masking — disable it so the rendered error message
        # shows the literal invalid value (the default mode masks every string).
        configure(masking={"masking_mode": "none"})

        @dataclass
        class Product:
            name: str
            sku: int

        @dataclass
        class Config:
            product: list[Product]

        metadata = Toml11Source(file=array_of_tables_error_last_toml_file)

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


class TestNoFilePathNoEnvVarLocation:
    """RemoteSource locations set both file_path and env_var_name to None.

    Regression: format_location() built the content lines (address + field/value) into
    `lines`, then discarded them with `return []` whenever file_path was None and the
    env_var_name branch didn't match — so VaultSource/ConsulSource errors never showed
    their remote address, no matter what resolve_location() produced.
    """

    def test_content_lines_are_not_discarded(self) -> None:
        errors = [
            FieldLoadError(
                field_path=["port"],
                message="invalid literal for int() with base 10: 'not_a_number'",
                input_value="not_a_number",
                locations=[
                    SourceLocation(
                        location_label="CONSUL",
                        file_path=None,
                        line_range=None,
                        line_content=["http://c:8500/v1/kv/myapp: port = not_a_number"],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc.exceptions[0]) == (
            "  [port]  invalid literal for int() with base 10: 'not_a_number'\n"
            "   ├── http://c:8500/v1/kv/myapp: port = not_a_number"
        )


class TestDefaultErrorDisplayFallback:
    def test_field_load_error_without_error_display_renders_80_3(self) -> None:
        """A FieldLoadError built without error_display still falls back to 80/3 (contract, not accident)."""
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
                        line_content=["b" * 81],
                        env_var_name=None,
                    ),
                ],
            ),
        ]
        exc = DatureConfigError("Config", errors)
        assert str(exc.exceptions[0]) == (
            f"  [timeout]  Expected int, got str\n   ├── {'b' * 77}...\n   └── FILE 'config.toml', line 2"
        )


class TestPerInstanceErrorDisplay:
    def test_two_instances_render_same_failure_differently(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"port": "{"x" * 100}"}}')

        @dataclass
        class Config:
            port: int

        narrow_conf = Dature(masking={"masking_mode": "none"})
        wide_conf = Dature(masking={"masking_mode": "none"}, error_display={"max_line_length": 200})

        with pytest.raises(DatureConfigError) as narrow_exc:
            narrow_conf.load(JsonSource(file=json_file), schema=Config)
        with pytest.raises(DatureConfigError) as wide_exc:
            wide_conf.load(JsonSource(file=json_file), schema=Config)

        narrow_line = str(narrow_exc.value.exceptions[0]).splitlines()[1]
        wide_line = str(wide_exc.value.exceptions[0]).splitlines()[1]
        assert narrow_line.strip().endswith("...")
        assert not wide_line.strip().endswith("...")

    def test_max_visible_lines_override(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("db:\n  host: localhost\n  port: abc\n")

        @dataclass
        class Config:
            db: int

        conf = Dature(masking={"masking_mode": "none"}, error_display={"max_visible_lines": 1})

        with pytest.raises(DatureConfigError) as exc_info:
            conf.load(Yaml12Source(file=yaml_file), schema=Config)

        assert str(exc_info.value.exceptions[0]) == (
            "  [db]  int() argument must be a string, a bytes-like object or a real number, not 'dict'\n"
            "   ├── ...\n"
            f"   └── FILE '{yaml_file}', line 1-3"
        )

    def test_raise_on_conflict_uses_instance_error_display(self, tmp_path: Path) -> None:
        a = tmp_path / "a.json"
        a.write_text(f'{{\n  "host": "{"a" * 40}"\n}}')

        b = tmp_path / "b.json"
        b.write_text(f'{{\n  "host": "{"b" * 40}"\n}}')

        @dataclass
        class Config:
            host: str

        conf = Dature(masking={"masking_mode": "none"}, error_display={"max_line_length": 20})

        with pytest.raises(MergeConflictError) as exc_info:
            conf.load(JsonSource(file=a), JsonSource(file=b), schema=Config, strategy="raise_on_conflict")

        assert str(exc_info.value.exceptions[0]) == (
            "  [host]  Conflicting values in multiple sources\n"
            f'   ├── "host": "{"a" * 8}...\n'
            "   │           ^^^^^^^^^\n"
            f"   └── FILE '{a}', line 2\n"
            f'   ├── "host": "{"b" * 8}...\n'
            "   │           ^^^^^^^^^\n"
            f"   └── FILE '{b}', line 2"
        )

    def test_except_star_preserves_leaf_error_display(self, tmp_path: Path) -> None:
        """derive() rebuilds only the group wrapper — leaves (and their error_display) survive except*."""
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"port": "{"x" * 100}"}}')

        @dataclass
        class Config:
            port: int

        conf = Dature(masking={"masking_mode": "none"}, error_display={"max_line_length": 200})

        matched: ExceptionGroup[FieldLoadError] | None = None
        try:
            conf.load(JsonSource(file=json_file), schema=Config)
        except* FieldLoadError as eg:
            matched = eg

        assert matched is not None
        rendered = str(matched.exceptions[0])
        assert not rendered.splitlines()[1].strip().endswith("...")


class TestDegenerateWidths:
    @pytest.mark.parametrize("max_line_length", [0, 1, 3, 4])
    def test_truncated_line_never_longer_than_input(self, max_line_length: int) -> None:
        line = "hello"
        errors = [
            FieldLoadError(
                field_path=["field"],
                message="bad",
                input_value=line,
                locations=[
                    SourceLocation(
                        location_label="FILE",
                        file_path=Path("config.toml"),
                        line_range=LineRange(start=1, end=1),
                        line_content=[line],
                        env_var_name=None,
                    ),
                ],
                error_display=ErrorDisplayConfig(max_line_length=max_line_length),
            ),
        ]
        exc = DatureConfigError("Config", errors)
        rendered = str(exc.exceptions[0])
        content_line = rendered.splitlines()[1].split("├── ", 1)[-1]
        assert len(content_line) <= len(line)
