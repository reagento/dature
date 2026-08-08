"""Integration tests for the VaultSource doc examples — require a live Vault container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

from pathlib import Path
from urllib.parse import urlparse

import pytest

from tests.example_helpers import DOCS_EXAMPLES_DIR, run_script

VAULT_EXAMPLES_DIR = DOCS_EXAMPLES_DIR / "advanced" / "remote" / "vault"


@pytest.fixture(scope="module")
def vault_examples_env(vault_container, vault_client) -> dict[str, str]:
    """Write the secret used by the examples and yield matching env vars."""
    vault_client.secrets.kv.v2.create_or_update_secret(
        path="myapp/config",
        secret={"db_password": "s3cret", "port": "5432", "name": "myapp"},
    )
    parsed = urlparse(vault_container.get_connection_url())
    return {
        "VAULT_HOST": parsed.hostname or "",
        "VAULT_PORT": str(parsed.port),
        "VAULT_SCHEME": parsed.scheme,
        "VAULT_TOKEN": vault_container.root_token,
    }


@pytest.mark.parametrize(
    "script",
    [pytest.param(p, id=p.name) for p in sorted(VAULT_EXAMPLES_DIR.rglob("*.py"))],
)
def test_example_script(script: Path, vault_examples_env: dict[str, str]) -> None:
    result = run_script(script, extra_env=vault_examples_env)
    assert result.returncode == 0, f"{script.name} failed:\nstderr:\n{result.stderr}"
    assert result.stderr == ""
    assert result.stdout == ""
