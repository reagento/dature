import os
import pathlib
import subprocess
import sys

import pytest

examples_dir = pathlib.Path(__file__).parent.parent / "examples"
example_scripts = sorted(examples_dir.rglob("*.py"))


@pytest.mark.parametrize("script_path", example_scripts, ids=lambda p: p.name)
def test_example_execution(script_path):
    env = os.environ.copy()

    project_root = pathlib.Path(__file__).parent.parent / "src"
    env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(  # noqa: PLW1510, S603
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, f"Script {script_path.name} Failed!\n\nError:\n{result.stderr}"
