"""Shared infrastructure for running ``examples/`` scripts as subprocesses in tests."""

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
PROJECT_SRC = Path(__file__).parent.parent / "src"

_IS_POSIX = hasattr(os, "posix_spawn")


@dataclass
class ScriptResult:
    returncode: int
    stdout: str
    stderr: str


def spawn_subprocess(argv: list[str], env: dict[str, str]) -> ScriptResult:
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


def build_env(script_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(script_path.parent), str(PROJECT_SRC), env.get("PYTHONPATH", "")]),
    )
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_script(
    script_path: Path,
    *,
    shim_dir: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> ScriptResult:
    """Run a ``.py`` or ``.sh`` example script and capture its output.

    ``shim_dir`` is required for ``.sh`` files (provides the ``dature`` CLI shim
    on PATH) and ignored for ``.py``. ``extra_env`` is merged on top of the
    script's default environment.
    """
    env = build_env(script_path)
    if extra_env:
        env.update(extra_env)

    if script_path.suffix == ".sh":
        if shim_dir is None:
            msg = "shim_dir is required for .sh scripts"
            raise ValueError(msg)
        env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
        bash = shutil.which("bash") or "/bin/bash"
        cmd = f"cd {shlex.quote(str(script_path.parent))} && exec {shlex.quote(bash)} {shlex.quote(str(script_path))}"
        return spawn_subprocess([bash, "-c", cmd], env)
    return spawn_subprocess([sys.executable, str(script_path)], env)


def resolve_placeholders(template: str, script_path: Path) -> str:
    sources_dir = str(script_path.parent / "sources") + os.sep
    shared_dir = str(script_path.parents[2] / "shared") + os.sep
    return template.replace("{SOURCES_DIR}", sources_dir).replace("{SHARED_DIR}", shared_dir)


def normalize_output(text: str) -> str:
    r"""Strip trailing whitespace and collapse path separators.

    Golden files are authored with POSIX-style ``/``; on Windows actual
    output uses ``\`` (or ``\\`` inside JSON-encoded strings). Replace
    both forms with ``/`` on both sides so comparisons are cross-platform.
    Order matters: drop ``\\`` first (otherwise ``\\`` becomes ``//``).
    """
    text = text.replace("\\\\", "/").replace("\\", "/")
    return "\n".join(line.rstrip() for line in text.splitlines())
