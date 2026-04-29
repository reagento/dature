import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass

import pytest

examples_dir = pathlib.Path(__file__).parent.parent / "examples"
example_scripts = sorted(examples_dir.rglob("*.py"))

_IS_POSIX = hasattr(os, "posix_spawn")


@dataclass
class ScriptResult:
    returncode: int
    stderr: str


def _run_via_posix_spawn(script_path: pathlib.Path, env: dict[str, str]) -> ScriptResult:
    """Use posix_spawn to avoid fork() segfaults on macOS CI."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    stderr_r, stderr_w = os.pipe()

    file_actions = [
        (os.POSIX_SPAWN_CLOSE, 0),
        (os.POSIX_SPAWN_DUP2, devnull, 1),
        (os.POSIX_SPAWN_DUP2, stderr_w, 2),
    ]

    pid = os.posix_spawn(
        sys.executable,
        [sys.executable, str(script_path)],
        env,
        file_actions=file_actions,
    )

    os.close(devnull)
    os.close(stderr_w)

    with os.fdopen(stderr_r) as stderr_f:
        stderr = stderr_f.read()

    _, wait_status = os.waitpid(pid, 0)
    returncode = os.waitstatus_to_exitcode(wait_status)

    return ScriptResult(returncode=returncode, stderr=stderr)


def _run_via_subprocess(script_path: pathlib.Path, env: dict[str, str]) -> ScriptResult:
    result = subprocess.run(  # noqa: PLW1510, S603
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        env=env,
    )
    return ScriptResult(returncode=result.returncode, stderr=result.stderr)


def _run_example(script_path: pathlib.Path) -> ScriptResult:
    project_root = pathlib.Path(__file__).parent.parent / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"

    if _IS_POSIX:
        return _run_via_posix_spawn(script_path, env)
    return _run_via_subprocess(script_path, env)


def _resolve_stderr_placeholders(template: str, script_path: pathlib.Path) -> str:
    sources_dir = str(script_path.parent / "sources") + os.sep
    shared_dir = str(script_path.parents[2] / "shared") + os.sep

    return template.replace("{SOURCES_DIR}", sources_dir).replace("{SHARED_DIR}", shared_dir).replace("{SEP}", os.sep)


def _normalize_trailing_whitespace(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines())


_success_scripts = [s for s in example_scripts if not s.with_suffix(".stderr").exists()]
_error_scripts = [s for s in example_scripts if s.with_suffix(".stderr").exists()]


@pytest.mark.parametrize("script_path", _success_scripts, ids=lambda p: p.name)
def test_example_execution(script_path: pathlib.Path) -> None:
    result = _run_example(script_path)
    assert result.returncode == 0, f"Script {script_path.name} Failed!\n\nError:\n{result.stderr}"


@pytest.mark.parametrize("script_path", _error_scripts, ids=lambda p: p.name)
def test_example_expected_error(script_path: pathlib.Path) -> None:
    result = _run_example(script_path)
    assert result.returncode != 0, f"Script {script_path.name} should have failed but exited with 0"

    stderr_file = script_path.with_suffix(".stderr")
    expected = _resolve_stderr_placeholders(stderr_file.read_text(), script_path)
    normalized_stderr = _normalize_trailing_whitespace(result.stderr)
    normalized_expected = _normalize_trailing_whitespace(expected.strip())
    assert normalized_expected in normalized_stderr, (
        f"Script {script_path.name} stderr mismatch.\n\n"
        f"Expected fragment:\n{expected.strip()}\n\n"
        f"Actual stderr:\n{result.stderr}"
    )
