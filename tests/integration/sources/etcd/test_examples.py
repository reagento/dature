"""Integration tests for the EtcdSource doc examples — require a live etcd container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

from pathlib import Path

import pytest

from tests.example_helpers import DOCS_EXAMPLES_DIR, run_script
from tests.integration.sources.etcd.helpers import etcd_address

ETCD_EXAMPLES_DIR = DOCS_EXAMPLES_DIR / "advanced" / "remote" / "etcd"


@pytest.fixture(scope="module")
def etcd_examples_env(etcd_container, etcd_client, etcd_internal_port) -> dict[str, str]:
    """Write the secret used by the examples and yield matching env vars."""
    etcd_client.put("myapp/db_password", "s3cret")
    etcd_client.put("myapp/port", "5432")
    etcd_client.put("myapp/name", "myapp")

    host, port = etcd_address(etcd_container, etcd_internal_port)
    return {
        "ETCD_HOST": host,
        "ETCD_PORT": str(port),
    }


@pytest.mark.parametrize(
    "script",
    [pytest.param(p, id=p.name) for p in sorted(ETCD_EXAMPLES_DIR.rglob("*.py"))],
)
def test_example_script(script: Path, etcd_examples_env: dict[str, str]) -> None:
    result = run_script(script, extra_env=etcd_examples_env)

    assert result.returncode == 0, f"{script.name} failed:\nstderr:\n{result.stderr}"
    assert result.stderr == ""
    assert result.stdout == ""
