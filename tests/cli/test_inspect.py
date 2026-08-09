"""End-to-end tests for ``dature inspect``."""

import json
import textwrap

import pytest

SCHEMA_DB = textwrap.dedent("""\
    from dataclasses import dataclass
    @dataclass
    class DB:
        host: str
        port: int
    @dataclass
    class Settings:
        db: DB
""")

SCHEMA_FLAT = textwrap.dedent("""\
    from dataclasses import dataclass
    @dataclass
    class S:
        host: str
        port: int
""")

SCHEMA_SECRET = textwrap.dedent("""\
    from dataclasses import dataclass
    @dataclass
    class S:
        host: str
        password: str
""")

SCHEMA_EMPTY = textwrap.dedent(
    """
    from dataclasses import dataclass

    @dataclass
    class Empty:
        pass
    """
)

NESTED_SCHEMA = textwrap.dedent(
    """
            from dataclasses import dataclass

            @dataclass
            class Credentials:
                username: str
                password: str

            @dataclass
            class DB:
                host: str
                port: int
                credentials: Credentials

            @dataclass
            class Settings:
                db: DB
            """
)


class TestInspectGoldenPath:
    def test_json_format(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_DB)
        cfg = cfg_file({"db": {"host": "localhost", "port": 5432}})

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "json",
        )
        assert code == 0
        assert err == ""
        assert json.loads(out) == {
            "schema": "Settings",
            "strategy": None,
            "sources": [
                {
                    "index": 0,
                    "file_path": str(cfg),
                    "loader_type": "json",
                    "raw_data": {"db": {"host": "localhost", "port": 5432}},
                },
            ],
            "field_origins": [
                {
                    "key": "db",
                    "value": {"host": "localhost", "port": 5432},
                    "source_index": 0,
                    "source_file": str(cfg),
                    "source_loader_type": "json",
                },
            ],
            "merged_data": {"db": {"host": "localhost", "port": 5432}},
        }

    def test_text_format(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_DB)
        cfg = cfg_file({"db": {"host": "localhost", "port": 5432}})

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "text",
        )
        expected_out = (
            "Schema: Settings (strategy: —)\n"
            "\n"
            "Sources:\n"
            f"  [0] json         {cfg}\n"
            "\n"
            "Field origins:\n"
            f'  db = {{"host": "localhost", "port": 5432}}   <- [0] {cfg}\n'
            "\n"
            "Merged data:\n"
            "  {\n"
            '    "db": {\n'
            '      "host": "localhost",\n'
            '      "port": 5432\n'
            "    }\n"
            "  }\n"
        )
        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_table_format(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_DB)
        cfg = cfg_file({"db": {"host": "localhost", "port": 5432}})

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "table",
        )
        source = str(cfg)
        expected_out = (
            f"+---------+{'-' * (len(source) + 2)}+-------------+\n"
            f"| key     | source{' ' * (len(source) - len('source'))} | value       |\n"
            f"+---------+{'-' * (len(source) + 2)}+-------------+\n"
            f"| db.host | {source} | 'localhost' |\n"
            f"| db.port | {source} | 5432        |\n"
            f"+---------+{'-' * (len(source) + 2)}+-------------+\n"
        )
        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_field_filter_in_table_format(
        self,
        run_cli,
        write_schema,
        cfg_file,
    ):
        write_schema(SCHEMA_DB)
        cfg = cfg_file(
            {
                "db": {
                    "host": "localhost",
                    "port": 5432,
                }
            }
        )

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--field",
            "db",
            "--format",
            "table",
        )

        source = str(cfg)
        expected_out = (
            f"+---------+{'-' * (len(source) + 2)}+-------------+\n"
            f"| key     | source{' ' * (len(source) - len('source'))} | value       |\n"
            f"+---------+{'-' * (len(source) + 2)}+-------------+\n"
            f"| db.host | {source} | 'localhost' |\n"
            f"| db.port | {source} | 5432        |\n"
            f"+---------+{'-' * (len(source) + 2)}+-------------+\n"
        )

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_table_format_masks_secrets(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_SECRET)
        cfg = cfg_file(
            {"host": "localhost", "password": "super_secret_password_123"},
        )

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:S",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "table",
        )

        source = str(cfg)
        expected_out = (
            f"+----------+{'-' * (len(source) + 2)}+--------------+\n"
            f"| key      | source{' ' * (len(source) - len('source'))} | value        |\n"
            f"+----------+{'-' * (len(source) + 2)}+--------------+\n"
            f"| host     | {source} | 'localhost'  |\n"
            f"| password | {source} | '<REDACTED>' |\n"
            f"+----------+{'-' * (len(source) + 2)}+--------------+\n"
        )

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_nested_dict_values_are_flattened_in_table(
        self,
        run_cli,
        write_schema,
        cfg_file,
    ):
        write_schema(NESTED_SCHEMA)

        cfg = cfg_file(
            {
                "db": {
                    "host": "localhost",
                    "port": 5432,
                    "credentials": {
                        "username": "admin",
                        "password": "secret",
                    },
                }
            }
        )

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "table",
        )

        source = str(cfg)

        rows = [
            ("db.host", "'localhost'"),
            ("db.port", "5432"),
            ("db.credentials.username", "'admin'"),
            ("db.credentials.password", "'<REDACTED>'"),
        ]

        key_width = max(len("key"), *(len(key) for key, _ in rows))
        source_width = max(len("source"), len(source))

        value_width = (
            max(
                len("value"),
                *(len(value) for _, value in rows),
            )
            + 2
        )

        separator = f"+{'-' * (key_width + 2)}+{'-' * (source_width + 2)}+{'-' * value_width}+\n"

        expected_out = separator
        expected_out += f"| {'key':<{key_width}} | {'source':<{source_width}} | {'value':<{value_width - 2}} |\n"
        expected_out += separator

        for key, value in rows:
            expected_out += f"| {key:<{key_width}} | {source:<{source_width}} | {value:<{value_width - 2}} |\n"

        expected_out += separator

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_field_filter_existing_but_missing_origin_in_table(
        self,
        run_cli,
        write_schema,
        cfg_file,
    ):
        write_schema(SCHEMA_DB)
        cfg = cfg_file(
            {
                "db": {
                    "host": "localhost",
                    "port": 5432,
                }
            }
        )

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--field",
            "db.port",
            "--format",
            "table",
        )

        expected_out = (
            "+-----+--------+-------+\n| key | source | value |\n+-----+--------+-------+\n+-----+--------+-------+\n"
        )

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_table_value_width_uses_header_when_values_are_shorter(
        self,
        run_cli,
        write_schema,
        cfg_file,
    ):
        write_schema(SCHEMA_FLAT)
        cfg = cfg_file(
            {
                "host": "x",
                "port": 1,
            }
        )

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:S",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "table",
        )

        source = str(cfg)
        expected_out = (
            f"+------+{'-' * (len(source) + 2)}+-------+\n"
            f"| key  | source{' ' * (len(source) - len('source'))} | value |\n"
            f"+------+{'-' * (len(source) + 2)}+-------+\n"
            f"| host | {source} | 'x'   |\n"
            f"| port | {source} | 1     |\n"
            f"+------+{'-' * (len(source) + 2)}+-------+\n"
        )

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_list_value_is_json_encoded_in_table(self, run_cli, write_schema, cfg_file):
        schema = textwrap.dedent(
            """
            from dataclasses import dataclass
            from typing import List

            @dataclass
            class S:
                hosts: List[str]
            """
        )
        write_schema(schema)
        cfg = cfg_file({"hosts": ["localhost", "db.example.com"]})

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:S",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "table",
        )

        source = str(cfg)
        value = '["localhost", "db.example.com"]'

        expected_out = (
            f"+-------+{'-' * (len(source) + 2)}+{'-' * (len(value) + 2)}+\n"
            f"| key   | source{' ' * (len(source) - len('source'))} "
            f"| value{' ' * (len(value) - len('value'))} |\n"
            f"+-------+{'-' * (len(source) + 2)}+{'-' * (len(value) + 2)}+\n"
            f"| hosts | {source} | {value} |\n"
            f"+-------+{'-' * (len(source) + 2)}+{'-' * (len(value) + 2)}+\n"
        )

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_multiple_sources_table_preserves_field_origins(
        self,
        run_cli,
        write_schema,
        cfg_file,
    ):
        write_schema(SCHEMA_FLAT)
        defaults = cfg_file(
            {"host": "default-host", "port": 3000},
            name="defaults.json",
        )
        overrides = cfg_file(
            {"port": 8080},
            name="overrides.json",
        )

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:S",
            "--source",
            f"type=dature.JsonSource,file={defaults}",
            "--source",
            f"type=dature.JsonSource,file={overrides}",
            "--strategy",
            "last_wins",
            "--format",
            "table",
        )

        source_defaults = str(defaults)
        source_overrides = str(overrides)
        source_width = max(
            len("source"),
            len(source_defaults),
            len(source_overrides),
        )

        expected_out = (
            f"+------+{'-' * (source_width + 2)}+----------------+\n"
            f"| key  | {'source':<{source_width}} | value          |\n"
            f"+------+{'-' * (source_width + 2)}+----------------+\n"
            f"| host | {source_defaults:<{source_width}} | 'default-host' |\n"
            f"| port | {source_overrides:<{source_width}} | 8080           |\n"
            f"+------+{'-' * (source_width + 2)}+----------------+\n"
        )

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_table_value_with_newline_documents_row_alignment(
        self,
        run_cli,
        write_schema,
        cfg_file,
    ):
        write_schema(SCHEMA_FLAT)
        cfg = cfg_file(
            {
                "host": "line1\nline2",
                "port": 1,
            }
        )

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:S",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "table",
        )

        source = str(cfg)
        source_width = max(len("source"), len(source))

        expected_out = (
            f"+------+{'-' * (source_width + 2)}+----------------+\n"
            f"| key  | {'source':<{source_width}} | value          |\n"
            f"+------+{'-' * (source_width + 2)}+----------------+\n"
            f"| host | {source:<{source_width}} | 'line1\\nline2' |\n"
            f"| port | {source:<{source_width}} | 1              |\n"
            f"+------+{'-' * (source_width + 2)}+----------------+\n"
        )

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_none_value_in_table(
        self,
        run_cli,
        write_schema,
        cfg_file,
    ):
        schema = textwrap.dedent(
            """
            from dataclasses import dataclass
            from typing import Optional

            @dataclass
            class S:
                host: Optional[str]
            """
        )
        write_schema(schema)
        cfg = cfg_file({"host": None})

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:S",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "table",
        )

        source = str(cfg)
        source_width = max(len("source"), len(source))

        expected_out = (
            f"+------+{'-' * (source_width + 2)}+-------+\n"
            f"| key  | {'source':<{source_width}} | value |\n"
            f"+------+{'-' * (source_width + 2)}+-------+\n"
            f"| host | {source:<{source_width}} | null  |\n"
            f"+------+{'-' * (source_width + 2)}+-------+\n"
        )

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_empty_report_in_table_format(
        self,
        run_cli,
        write_schema,
        cfg_file,
    ):
        write_schema(SCHEMA_EMPTY)
        cfg = cfg_file({})

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Empty",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--format",
            "table",
        )

        expected_out = (
            "+-----+--------+-------+\n| key | source | value |\n+-----+--------+-------+\n+-----+--------+-------+\n"
        )

        assert code == 0
        assert err == ""
        assert out == expected_out

    def test_field_filter(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_DB)
        cfg = cfg_file({"db": {"host": "localhost", "port": 5432}})

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--field",
            "db.port",
            "--format",
            "json",
        )
        assert code == 0
        assert err == ""
        assert json.loads(out) == {
            "schema": "Settings",
            "strategy": None,
            "sources": [
                {
                    "index": 0,
                    "file_path": str(cfg),
                    "loader_type": "json",
                    "raw_data": {"db": {"host": "localhost", "port": 5432}},
                },
            ],
            "field_origins": [],
            "merged_data": 5432,
        }

    def test_multiple_sources_strategy(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_FLAT)
        defaults = cfg_file({"host": "default-host", "port": 3000}, name="defaults.json")
        overrides = cfg_file({"port": 8080}, name="overrides.json")

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:S",
            "--source",
            f"type=dature.JsonSource,file={defaults}",
            "--source",
            f"type=dature.JsonSource,file={overrides}",
            "--strategy",
            "last_wins",
            "--format",
            "json",
        )
        assert code == 0
        assert err == ""
        assert json.loads(out) == {
            "schema": "S",
            "strategy": "SourceLastWins",
            "sources": [
                {
                    "index": 0,
                    "file_path": str(defaults),
                    "loader_type": "json",
                    "raw_data": {"host": "default-host", "port": 3000},
                },
                {
                    "index": 1,
                    "file_path": str(overrides),
                    "loader_type": "json",
                    "raw_data": {"port": 8080},
                },
            ],
            "field_origins": [
                {
                    "key": "host",
                    "value": "default-host",
                    "source_index": 0,
                    "source_file": str(defaults),
                    "source_loader_type": "json",
                },
                {
                    "key": "port",
                    "value": 8080,
                    "source_index": 1,
                    "source_file": str(overrides),
                    "source_loader_type": "json",
                },
            ],
            "merged_data": {"host": "default-host", "port": 8080},
        }


class TestInspectErrors:
    @pytest.mark.parametrize(
        ("schema_arg", "source_arg", "expected_err"),
        [
            (
                "no_such_module:X",
                "type=dature.JsonSource,file=/tmp/x.json",
                "error: No module named 'no_such_module'\n",
            ),
            (
                "myschema:NoSuchClass",
                "type=dature.JsonSource,file=/tmp/x.json",
                "error: module 'myschema' has no attribute 'NoSuchClass'\n",
            ),
            (
                "myschema:Settings",
                "type=os.path,file=/tmp/x.json",
                "error: 'os.path' is not a class\n",
            ),
            (
                "myschema:Settings",
                "broken-spec",
                "error: Invalid source kwarg 'broken-spec': expected 'key=value'\n",
            ),
        ],
    )
    def test_setup_errors(self, run_cli, write_schema, schema_arg, source_arg, expected_err):
        write_schema(SCHEMA_DB)
        code, out, err = run_cli(
            "inspect",
            "--schema",
            schema_arg,
            "--source",
            source_arg,
        )
        assert code == 2
        assert out == ""
        assert err == expected_err

    def test_missing_file(self, run_cli, write_schema, tmp_path):
        write_schema(SCHEMA_DB)
        nope = tmp_path / "nope.json"
        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={nope}",
        )
        assert code == 1
        assert out == ""
        assert err == (
            "  | dature.errors.exceptions.DatureConfigError: Settings loading errors (1)\n"
            "  +-+---------------- 1 ----------------\n"
            f"    | FileNotFoundError: Config file not found: {nope}\n"
            "    +------------------------------------\n"
            "\n"
        )

    def test_field_filter_missing_in_table_format(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_DB)
        cfg = cfg_file({"db": {"host": "localhost", "port": 5432}})

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--field",
            "db.nonexistent",
            "--format",
            "table",
        )

        assert code == 1
        assert out == ""
        assert err == "error: \"Field 'db.nonexistent' not found in merged data\"\n"

    def test_field_filter_missing(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_DB)
        cfg = cfg_file({"db": {"host": "localhost", "port": 5432}})

        code, out, err = run_cli(
            "inspect",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--field",
            "db.nonexistent",
        )
        assert code == 1
        assert out == ""
        assert err == "error: \"Field 'db.nonexistent' not found in merged data\"\n"
