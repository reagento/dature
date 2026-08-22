"""Tests for dature.mypy_plugin: plugin must make @load()-decorated class instantiable."""

import textwrap
from pathlib import Path

import mypy.api
import pytest

_DECORATED_SRC = textwrap.dedent("""\
    from dataclasses import dataclass
    from dature import load
    from dature.sources.env_ import EnvSource

    @load(EnvSource())
    @dataclass
    class Config:
        host: str
        port: int

    Config()  # all args optional when plugin is active
""")

_POSITIONAL_SCHEMA_SRC = textwrap.dedent("""\
    from dataclasses import dataclass
    from dature import load
    from dature.sources.env_ import EnvSource

    @dataclass
    class Config:
        host: str
        port: int

    load(EnvSource(), Config)  # schema is keyword-only, must be load(..., schema=Config)
""")

_MYPY_BASE_CFG = "[mypy]\nignore_missing_imports = True\n"
_MYPY_PLUGIN_CFG = _MYPY_BASE_CFG + "plugins = dature.mypy_plugin\n"


def _run_mypy(tmp_path: Path, src: str, mypy_cfg: str) -> tuple[str, int]:
    py_file = tmp_path / "cfg.py"
    py_file.write_text(src)
    ini = tmp_path / "mypy.ini"
    ini.write_text(mypy_cfg)
    stdout, _, rc = mypy.api.run([str(py_file), "--no-error-summary", f"--config-file={ini}"])
    return stdout, rc


@pytest.mark.parametrize(
    ("src", "mypy_cfg", "expect_rc_zero", "expected_error_code"),
    [
        (_DECORATED_SRC, _MYPY_PLUGIN_CFG, True, None),
        (_DECORATED_SRC, _MYPY_BASE_CFG, False, "call-arg"),
        (_POSITIONAL_SCHEMA_SRC, _MYPY_BASE_CFG, False, "call-overload"),
    ],
    ids=[
        "plugin_allows_no_arg_instantiation",
        "without_plugin_reports_missing_args",
        "positional_schema_reports_call_overload",
    ],
)
def test_mypy_check(
    tmp_path: Path,
    src: str,
    mypy_cfg: str,
    expect_rc_zero: bool,
    expected_error_code: str | None,
) -> None:
    stdout, rc = _run_mypy(tmp_path, src, mypy_cfg)

    if expect_rc_zero:
        assert rc == 0, f"Unexpected mypy errors:\n{stdout}"
    else:
        assert rc != 0, f"Expected mypy to report an error, got none:\n{stdout}"
        assert expected_error_code is not None
        assert expected_error_code in stdout
