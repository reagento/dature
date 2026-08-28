"""Integration tests for the ZookeeperSource doc examples — require a live ZooKeeper container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from kazoo.client import KazooClient

from tests.example_helpers import DOCS_EXAMPLES_DIR, run_script
from tests.integration.sources.zookeeper.helpers import drop_znodes, seed_znodes, zk_address

ZOOKEEPER_EXAMPLES_DIR = DOCS_EXAMPLES_DIR / "advanced" / "remote" / "zookeeper"


@pytest.fixture(scope="module")
def zk_examples_env(zk_container, zk_client: KazooClient, zk_internal_port) -> Generator[dict[str, str]]:
    """Write the secret used by the examples and yield the matching env var."""
    seed_znodes(
        zk_client,
        "/myapp",
        {"/myapp/db_password": b"s3cret", "/myapp/port": b"5432", "/myapp/name": b"myapp"},
    )

    host, port = zk_address(zk_container, zk_internal_port)
    yield {
        "ZK_HOST": f"{host}:{port}",
    }
    drop_znodes(zk_client, "/myapp")


@pytest.mark.parametrize(
    "script",
    [pytest.param(p, id=p.name) for p in sorted(ZOOKEEPER_EXAMPLES_DIR.rglob("*.py"))],
)
def test_example_script(script: Path, zk_examples_env: dict[str, str]) -> None:
    result = run_script(script, extra_env=zk_examples_env)

    assert result.returncode == 0, f"{script.name} failed:\nstderr:\n{result.stderr}"
    assert result.stderr == ""
    assert result.stdout == ""
