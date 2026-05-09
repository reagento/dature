from pathlib import Path

import pytest

from tests.example_helpers import (
    EXAMPLES_DIR,
    normalize_output,
    resolve_placeholders,
    run_script,
)

# When a .sh file shares stem and parent with a .py file, the .sh is the
# canonical entry point (it usually invokes the .py with realistic args).
# Skip the .py from direct execution to avoid double-running with mismatched argv.
_sh_stems = {p.with_suffix("") for p in EXAMPLES_DIR.rglob("*.sh")}
# Examples needing live infrastructure (e.g. Vault) are exercised by the integration
# suite under tests/integration/sources/ — keep them out of the generic runner.
_INFRA_DIRS = {"remote_source"}
example_scripts = sorted(
    p
    for p in (*EXAMPLES_DIR.rglob("*.py"), *EXAMPLES_DIR.rglob("*.sh"))
    if (p.suffix == ".sh" or p.with_suffix("") not in _sh_stems) and not _INFRA_DIRS.intersection(p.parts)
)

_error_scripts = [s for s in example_scripts if s.with_suffix(".stderr").exists()]
_stdout_scripts = [s for s in example_scripts if s.with_suffix(".stdout").exists()]
_success_scripts = [s for s in example_scripts if s not in _error_scripts and s not in _stdout_scripts]


@pytest.mark.parametrize("script_path", _success_scripts, ids=lambda p: p.name)
def test_example_execution(script_path: Path, dature_shim_dir: Path) -> None:
    result = run_script(script_path, shim_dir=dature_shim_dir)
    assert result.returncode == 0, f"Script {script_path.name} failed!\n\nstderr:\n{result.stderr}"


@pytest.mark.parametrize("script_path", _error_scripts, ids=lambda p: p.name)
def test_example_expected_error(script_path: Path, dature_shim_dir: Path) -> None:
    result = run_script(script_path, shim_dir=dature_shim_dir)
    assert result.returncode != 0, f"Script {script_path.name} should have failed but exited with 0"

    expected = resolve_placeholders(script_path.with_suffix(".stderr").read_text(), script_path)
    assert normalize_output(expected.strip()) in normalize_output(result.stderr), (
        f"Script {script_path.name} stderr mismatch.\n\n"
        f"Expected fragment:\n{expected.strip()}\n\nActual stderr:\n{result.stderr}"
    )


@pytest.mark.parametrize("script_path", _stdout_scripts, ids=lambda p: p.name)
def test_example_expected_stdout(script_path: Path, dature_shim_dir: Path) -> None:
    result = run_script(script_path, shim_dir=dature_shim_dir)
    assert result.returncode == 0, (
        f"Script {script_path.name} failed (returncode={result.returncode})\n\nstderr:\n{result.stderr}"
    )

    expected = resolve_placeholders(script_path.with_suffix(".stdout").read_text(), script_path)
    assert normalize_output(expected.strip()) in normalize_output(result.stdout), (
        f"Script {script_path.name} stdout mismatch.\n\n"
        f"Expected fragment:\n{expected.strip()}\n\nActual stdout:\n{result.stdout}"
    )
