"""Integration tests for the AwsSecretsManagerSource doc examples — require a live LocalStack container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

import json
from pathlib import Path

import pytest

from tests.example_helpers import DOCS_EXAMPLES_DIR, run_script

SECRETS_MANAGER_EXAMPLES_DIR = DOCS_EXAMPLES_DIR / "advanced" / "remote" / "secrets_manager"


@pytest.fixture(scope="module")
def secrets_manager_examples_env(localstack_container, secrets_manager_put_secret) -> dict[str, str]:
    """Write the secret used by the examples and yield matching env vars."""
    secret = {"db_password": "s3cret", "port": 5432, "name": "myapp"}
    secrets_manager_put_secret(name="myapp/config", secret_string=json.dumps(secret))

    return {
        "SECRETS_MANAGER_ENDPOINT_URL": localstack_container.get_url(),
        "SECRETS_MANAGER_REGION_NAME": localstack_container.region_name,
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
    }


@pytest.mark.parametrize(
    "script",
    [pytest.param(p, id=p.name) for p in sorted(SECRETS_MANAGER_EXAMPLES_DIR.rglob("*.py"))],
)
def test_example_script(script: Path, secrets_manager_examples_env: dict[str, str]) -> None:
    result = run_script(script, extra_env=secrets_manager_examples_env)

    assert result.returncode == 0, f"{script.name} failed:\nstderr:\n{result.stderr}"
    assert result.stderr == ""
    assert result.stdout == ""
