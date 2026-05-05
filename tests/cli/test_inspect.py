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
                "error: 'os.path' is not a subclass of dature.Source\n",
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
        assert err == f"error: Config file not found: {nope}\n"
