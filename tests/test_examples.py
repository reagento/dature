import os
import pathlib
import subprocess
import sys

import pytest

examples_dir = pathlib.Path(__file__).parent.parent / "examples"
example_scripts = sorted(examples_dir.rglob("*.py"))


def _run_example(script_path: pathlib.Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()

    project_root = pathlib.Path(__file__).parent.parent / "src"
    env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")

    # process_group=0 forces posix_spawn instead of fork on macOS,
    # avoiding segfaults in subprocess._execute_child (CPython + macOS CI)
    return subprocess.run(  # noqa: PLW1510, S603
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        env=env,
        process_group=0,
    )


def _resolve_stderr_placeholders(template: str, script_path: pathlib.Path) -> str:
    sources_dir = str(script_path.parent / "sources")
    shared_dir = str(script_path.parents[2] / "shared")

    return template.replace("{SOURCES_DIR}", sources_dir).replace("{SHARED_DIR}", shared_dir)


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
