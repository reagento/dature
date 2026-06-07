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

_MYPY_BASE_CFG = "[mypy]\nignore_missing_imports = True\n"
_MYPY_PLUGIN_CFG = _MYPY_BASE_CFG + "plugins = dature.mypy_plugin\n"


@pytest.fixture
def cfg_file(tmp_path: Path) -> Path:
    p = tmp_path / "cfg.py"
    p.write_text(_DECORATED_SRC)
    return p


def _run_mypy(src: Path, mypy_cfg: str) -> tuple[str, int]:
    ini = src.parent / "mypy.ini"
    ini.write_text(mypy_cfg)
    stdout, _, rc = mypy.api.run([str(src), "--no-error-summary", f"--config-file={ini}"])
    return stdout, rc


def test_plugin_allows_no_arg_instantiation(cfg_file: Path) -> None:
    stdout, rc = _run_mypy(cfg_file, _MYPY_PLUGIN_CFG)

    assert rc == 0, f"Unexpected mypy errors with plugin:\n{stdout}"


def test_without_plugin_reports_missing_args(cfg_file: Path) -> None:
    stdout, rc = _run_mypy(cfg_file, _MYPY_BASE_CFG)

    assert rc != 0, "Expected mypy to report missing args without plugin"
    assert "call-arg" in stdout
