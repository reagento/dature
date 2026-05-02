import os
import pathlib
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass

import pytest

EXAMPLES_DIR = pathlib.Path(__file__).parent.parent / "examples"
PROJECT_SRC = pathlib.Path(__file__).parent.parent / "src"

# When a .sh file shares stem and parent with a .py file, the .sh is the
# canonical entry point (it usually invokes the .py with realistic args).
# Skip the .py from direct execution to avoid double-running with mismatched argv.
_sh_stems = {p.with_suffix("") for p in EXAMPLES_DIR.rglob("*.sh")}
example_scripts = sorted(
    p
    for p in (*EXAMPLES_DIR.rglob("*.py"), *EXAMPLES_DIR.rglob("*.sh"))
    if p.suffix == ".sh" or p.with_suffix("") not in _sh_stems
)

_IS_POSIX = hasattr(os, "posix_spawn")


@dataclass
class ScriptResult:
    returncode: int
    stdout: str
    stderr: str


def _spawn(argv: list[str], env: dict[str, str]) -> ScriptResult:
    """Run ``argv``, capture stdout/stderr/returncode.

    On POSIX, uses ``os.posix_spawn`` to avoid macOS fork() segfaults; on Windows,
    falls back to ``subprocess.run``.
    """
    if not _IS_POSIX:
        result = subprocess.run(argv, capture_output=True, text=True, env=env, check=False)  # noqa: S603
        return ScriptResult(result.returncode, result.stdout, result.stderr)

    stdout_r, stdout_w = os.pipe()
    stderr_r, stderr_w = os.pipe()
    file_actions = [
        (os.POSIX_SPAWN_CLOSE, 0),
        (os.POSIX_SPAWN_DUP2, stdout_w, 1),
        (os.POSIX_SPAWN_DUP2, stderr_w, 2),
    ]
    pid = os.posix_spawn(argv[0], argv, env, file_actions=file_actions)
    os.close(stdout_w)
    os.close(stderr_w)

    with os.fdopen(stdout_r) as f:
        stdout = f.read()
    with os.fdopen(stderr_r) as f:
        stderr = f.read()
    _, wait_status = os.waitpid(pid, 0)
    return ScriptResult(os.waitstatus_to_exitcode(wait_status), stdout, stderr)


def _build_env(script_path: pathlib.Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(script_path.parent), str(PROJECT_SRC), env.get("PYTHONPATH", "")]),
    )
    env["PYTHONIOENCODING"] = "utf-8"
    return env


@pytest.fixture(scope="session")
def dature_shim_dir(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """Provide a directory with a ``dature`` shim that proxies to ``python -m dature.cli``."""
    shim_dir = tmp_path_factory.mktemp("dature-shim")
    shim = shim_dir / "dature"
    shim.write_text(f'#!/usr/bin/env bash\nexec "{sys.executable}" -m dature.cli "$@"\n')
    shim.chmod(0o755)
    return shim_dir


def _run_example(script_path: pathlib.Path, shim_dir: pathlib.Path) -> ScriptResult:
    env = _build_env(script_path)
    if script_path.suffix == ".sh":
        env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
        bash = shutil.which("bash") or "/bin/bash"
        cmd = f"cd {shlex.quote(str(script_path.parent))} && exec {shlex.quote(bash)} {shlex.quote(str(script_path))}"
        return _spawn([bash, "-c", cmd], env)
    return _spawn([sys.executable, str(script_path)], env)


def _resolve_placeholders(template: str, script_path: pathlib.Path) -> str:
    sources_dir = str(script_path.parent / "sources") + os.sep
    shared_dir = str(script_path.parents[2] / "shared") + os.sep
    return template.replace("{SOURCES_DIR}", sources_dir).replace("{SHARED_DIR}", shared_dir).replace("{SEP}", os.sep)


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines())


_error_scripts = [s for s in example_scripts if s.with_suffix(".stderr").exists()]
_stdout_scripts = [s for s in example_scripts if s.with_suffix(".stdout").exists()]
_success_scripts = [s for s in example_scripts if s not in _error_scripts and s not in _stdout_scripts]


@pytest.mark.parametrize("script_path", _success_scripts, ids=lambda p: p.name)
def test_example_execution(script_path: pathlib.Path, dature_shim_dir: pathlib.Path) -> None:
    result = _run_example(script_path, dature_shim_dir)
    assert result.returncode == 0, f"Script {script_path.name} failed!\n\nstderr:\n{result.stderr}"


@pytest.mark.parametrize("script_path", _error_scripts, ids=lambda p: p.name)
def test_example_expected_error(script_path: pathlib.Path, dature_shim_dir: pathlib.Path) -> None:
    result = _run_example(script_path, dature_shim_dir)
    assert result.returncode != 0, f"Script {script_path.name} should have failed but exited with 0"

    expected = _resolve_placeholders(script_path.with_suffix(".stderr").read_text(), script_path)
    assert _normalize(expected.strip()) in _normalize(result.stderr), (
        f"Script {script_path.name} stderr mismatch.\n\n"
        f"Expected fragment:\n{expected.strip()}\n\nActual stderr:\n{result.stderr}"
    )


@pytest.mark.parametrize("script_path", _stdout_scripts, ids=lambda p: p.name)
def test_example_expected_stdout(script_path: pathlib.Path, dature_shim_dir: pathlib.Path) -> None:
    result = _run_example(script_path, dature_shim_dir)
    assert result.returncode == 0, (
        f"Script {script_path.name} failed (returncode={result.returncode})\n\nstderr:\n{result.stderr}"
    )

    expected = _resolve_placeholders(script_path.with_suffix(".stdout").read_text(), script_path)
    assert _normalize(expected.strip()) in _normalize(result.stdout), (
        f"Script {script_path.name} stdout mismatch.\n\n"
        f"Expected fragment:\n{expected.strip()}\n\nActual stdout:\n{result.stdout}"
    )
