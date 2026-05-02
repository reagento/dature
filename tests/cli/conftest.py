import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dature.cli import main


@pytest.fixture
def run_cli(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., tuple[int, str, str]]:
    """Invoke ``dature.cli.main`` with given args, return (exit_code, stdout, stderr).

    ``main()`` reads ``sys.argv`` directly (via ``ArgparseSource``); we
    override it per call instead of passing argv as an argument.
    """

    def _run(*args: str) -> tuple[int, str, str]:
        monkeypatch.setattr(sys, "argv", ["dature", *args])
        try:
            exit_code = main()
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 0
        captured = capsys.readouterr()
        return exit_code, captured.out, captured.err

    return _run


@pytest.fixture
def write_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., str]:
    """Write a schema module under ``tmp_path`` and make it importable.

    Returns the module name. Default name ``myschema``.
    """
    monkeypatch.syspath_prepend(str(tmp_path))

    def _write(source: str, name: str = "myschema") -> str:
        (tmp_path / f"{name}.py").write_text(source)
        sys.modules.pop(name, None)
        return name

    return _write


@pytest.fixture
def cfg_file(tmp_path: Path) -> Callable[..., Path]:
    """Write a JSON config file under tmp_path; returns its path."""
    counter = {"n": 0}

    def _write(payload: Any, name: str | None = None) -> Path:
        counter["n"] += 1
        filename = name or f"cfg_{counter['n']}.json"
        path = tmp_path / filename
        path.write_text(json.dumps(payload))
        return path

    return _write
