"""Integration tests for the AwsSsmSource doc examples — require a live LocalStack container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

from pathlib import Path

import pytest

from tests.example_helpers import DOCS_EXAMPLES_DIR, run_script

SSM_EXAMPLES_DIR = DOCS_EXAMPLES_DIR / "advanced" / "remote" / "ssm"


@pytest.fixture(scope="module")
def ssm_examples_env(localstack_container, ssm_client) -> dict[str, str]:
    """Write the secret used by the examples and yield matching env vars."""
    ssm_client.put_parameter(Name="/myapp/db_password", Value="s3cret", Type="String", Overwrite=True)
    ssm_client.put_parameter(Name="/myapp/port", Value="5432", Type="String", Overwrite=True)
    ssm_client.put_parameter(Name="/myapp/name", Value="myapp", Type="String", Overwrite=True)

    return {
        "SSM_ENDPOINT_URL": localstack_container.get_url(),
        "SSM_REGION_NAME": localstack_container.region_name,
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
    }


@pytest.mark.parametrize(
    "script",
    [pytest.param(p, id=p.name) for p in sorted(SSM_EXAMPLES_DIR.rglob("*.py"))],
)
def test_example_script(script: Path, ssm_examples_env: dict[str, str]) -> None:
    result = run_script(script, extra_env=ssm_examples_env)

    assert result.returncode == 0, f"{script.name} failed:\nstderr:\n{result.stderr}"
    assert result.stderr == ""
    assert result.stdout == ""
