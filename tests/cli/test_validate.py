"""End-to-end tests for ``dature validate``."""

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


class TestValidateSuccess:
    def test_single_source(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_DB)
        cfg = cfg_file({"db": {"host": "localhost", "port": 5432}})
        code, out, err = run_cli(
            "validate",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
        )
        assert code == 0
        assert out == "OK\n"
        assert err == ""

    def test_multiple_sources(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_DB)
        a = cfg_file({"db": {"host": "h", "port": 1}}, name="a.json")
        b = cfg_file({"db": {"port": 2}}, name="b.json")
        code, out, err = run_cli(
            "validate",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={a}",
            "--source",
            f"type=dature.JsonSource,file={b}",
            "--strategy",
            "last_wins",
        )
        assert code == 0
        assert out == "OK\n"
        assert err == ""

    def test_secret_field_names_repeated(self, run_cli, write_schema, cfg_file):
        """Regression: argparse ``action=append`` gives list, but ``load()`` expects
        ``tuple[str, ...]`` for ``secret_field_names``; downstream uses it as a
        dict cache key (must be hashable). A list crashes with ``TypeError``.
        """
        schema = "from dataclasses import dataclass\n@dataclass\nclass S:\n    password: str\n    host: str\n"
        write_schema(schema)
        cfg = cfg_file({"password": "secret123", "host": "localhost"})
        code, out, err = run_cli(
            "validate",
            "--schema",
            "myschema:S",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
            "--mask-secrets",
            "--secret-field-names",
            "password",
            "--secret-field-names",
            "api_key",
        )
        assert code == 0
        assert out == "OK\n"
        assert err == ""


class TestValidateFailures:
    def test_type_mismatch(self, run_cli, write_schema, cfg_file):
        write_schema(SCHEMA_DB)
        cfg = cfg_file({"db": {"host": "localhost", "port": "not_a_number"}})
        code, out, err = run_cli(
            "validate",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={cfg}",
        )
        expected_err = (
            "  | dature.errors.exceptions.DatureConfigError: Settings loading errors (1)\n"
            "  +-+---------------- 1 ----------------\n"
            "    | dature.errors.exceptions.FieldLoadError:"
            "   [db.port]  invalid literal for int() with base 10: 'not_a_number'\n"
            '    |    ├── {"db": {"host": "localhost", "port": "not_a_number"}}\n'
            "    |    │                                         ^^^^^^^^^^^^\n"
            f"    |    └── FILE '{cfg}', line 1\n"
            "    +------------------------------------\n"
            "\n"
        )
        assert code == 1
        assert out == ""
        assert err == expected_err

    def test_missing_file(self, run_cli, write_schema, tmp_path):
        write_schema(SCHEMA_DB)
        absent = tmp_path / "absent.json"
        code, out, err = run_cli(
            "validate",
            "--schema",
            "myschema:Settings",
            "--source",
            f"type=dature.JsonSource,file={absent}",
        )
        assert code == 1
        assert out == ""
        assert err == (
            "  | dature.errors.exceptions.DatureConfigError: Settings loading errors (1)\n"
            "  +-+---------------- 1 ----------------\n"
            f"    | FileNotFoundError: Config file not found: {absent}\n"
            "    +------------------------------------\n"
            "\n"
        )

    @pytest.mark.parametrize(
        ("schema_arg", "source_arg", "expected_err"),
        [
            (
                "nope:X",
                "type=dature.JsonSource,file=/tmp/x.json",
                "error: No module named 'nope'\n",
            ),
            (
                "myschema:Missing",
                "type=dature.JsonSource,file=/tmp/x.json",
                "error: module 'myschema' has no attribute 'Missing'\n",
            ),
            (
                "myschema:Settings",
                "type=os.path,file=/tmp/x.json",
                "error: 'os.path' is not a class\n",
            ),
            (
                "myschema:Settings",
                "no_type=here",
                "error: Missing required 'type=...' in source spec: 'no_type=here'\n",
            ),
        ],
    )
    def test_setup_errors(self, run_cli, write_schema, schema_arg, source_arg, expected_err):
        write_schema(SCHEMA_DB)
        code, out, err = run_cli(
            "validate",
            "--schema",
            schema_arg,
            "--source",
            source_arg,
        )
        assert code == 2
        assert out == ""
        assert err == expected_err
