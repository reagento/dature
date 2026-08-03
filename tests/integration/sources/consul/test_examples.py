"""Integration tests for the ConsulSource doc examples — require a live Consul container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

from pathlib import Path

import pytest

from tests.example_helpers import DOCS_EXAMPLES_DIR, run_script

CONSUL_EXAMPLES_DIR = DOCS_EXAMPLES_DIR / "advanced" / "remote" / "consul"


@pytest.fixture(scope="module")
def consul_examples_env(consul_container, consul_client, consul_port) -> dict[str, str]:
    """Write the secret used by the examples and yield matching env vars."""
    consul_client.kv.put("myapp/db_password", "s3cret")
    consul_client.kv.put("myapp/port", "5432")
    consul_client.kv.put("myapp/name", "myapp")
    return {
        "CONSUL_HOST": consul_container.get_container_host_ip(),
        "CONSUL_PORT": str(consul_container.get_exposed_port(consul_port)),
    }


@pytest.mark.parametrize(
    "script",
    [pytest.param(p, id=p.name) for p in sorted(CONSUL_EXAMPLES_DIR.rglob("*.py"))],
)
def test_example_script(script: Path, consul_examples_env: dict[str, str]) -> None:
    result = run_script(script, extra_env=consul_examples_env)
    assert result.returncode == 0, f"{script.name} failed:\nstderr:\n{result.stderr}"
    assert result.stderr == ""
    assert result.stdout == ""
