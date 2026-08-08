"""Shared fixtures for AWS-backed (``ssm``/``secrets_manager``) integration tests.

One LocalStack container running both services, shared across ``sources/ssm/`` and
``sources/secrets_manager/`` — a second container would double the cost of pulling
LocalStack's ~511 MB image for no benefit, since a single instance already runs both.
"""

from collections.abc import Generator

import pytest
from testcontainers.community.localstack import LocalStackContainer

# Keep this on a community-compatible image. Calendar-versioned LocalStack images
# can require LocalStack Cloud auth/license and fail CI before services start.
LOCALSTACK_IMAGE = "localstack/localstack:3.8.1"


@pytest.fixture(scope="session")
def localstack_container() -> Generator[LocalStackContainer]:
    """One LocalStack container running SSM and Secrets Manager, shared for the whole run."""
    container = LocalStackContainer(LOCALSTACK_IMAGE).with_services("ssm", "secretsmanager")
    # Default start() timeout (60s) only covers wait_for_logs, not the ~511 MB image pull —
    # a cold runner can miss it, so give the pull room to finish before we start polling.
    container.start(timeout=120)
    try:
        yield container
    finally:
        container.stop()
