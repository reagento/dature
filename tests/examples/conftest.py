"""Auto-mark every test under ``tests/examples/`` with ``@pytest.mark.examples``.

Also provides the ``dature_shim_dir`` session fixture that puts a thin
``dature`` CLI shim on ``PATH`` for ``.sh`` example scripts.
"""

import sys
from pathlib import Path

import pytest

_EXAMPLES_ROOT = Path(__file__).parent.resolve()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if _EXAMPLES_ROOT in Path(item.fspath).resolve().parents:
            item.add_marker(pytest.mark.examples)


@pytest.fixture(scope="session")
def dature_shim_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Provide a directory with a ``dature`` shim that proxies to ``python -m dature.cli``."""
    shim_dir = tmp_path_factory.mktemp("dature-shim")
    shim = shim_dir / "dature"
    shim.write_text(f'#!/usr/bin/env bash\nexec "{sys.executable}" -m dature.cli "$@"\n')
    shim.chmod(0o755)
    return shim_dir
