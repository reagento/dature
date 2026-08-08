"""Shared fixtures for AWS-backed (``ssm``/``secrets_manager``) integration tests.

One LocalStack container running both services, shared across ``sources/ssm/`` and
``sources/secrets_manager/`` — a second container would double the cost of pulling
LocalStack's ~511 MB image for no benefit, since a single instance already runs both.
"""

from collections.abc import Generator
from uuid import uuid4

import pytest
from testcontainers.community.localstack import LocalStackContainer

# Keep this on a community-compatible image. Calendar-versioned LocalStack images
# can require LocalStack Cloud auth/license and fail CI before services start.
LOCALSTACK_IMAGE = "localstack/localstack:3.8.1"


@pytest.fixture(scope="session")
def localstack_container() -> Generator[LocalStackContainer]:
    """One LocalStack container running SSM and Secrets Manager, shared for the whole run."""
    container = LocalStackContainer(LOCALSTACK_IMAGE).with_services("iam", "ssm", "secretsmanager")
    # Default start() timeout (60s) only covers wait_for_logs, not the ~511 MB image pull —
    # a cold runner can miss it, so give the pull room to finish before we start polling.
    container.start(timeout=120)
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def localstack_iam_credentials(localstack_container) -> dict[str, str]:
    """Create IAM user credentials accepted by LocalStack community.

    LocalStack community maps access keys to IAM principals, but it does not
    enforce IAM policies or reject mismatched secret keys.
    """
    iam_client = localstack_container.get_client("iam")
    user_name = f"dature-auth-{uuid4().hex}"
    iam_client.create_user(UserName=user_name)
    response = iam_client.create_access_key(UserName=user_name)
    access_key = response["AccessKey"]
    return {
        "aws_access_key_id": access_key["AccessKeyId"],
        "aws_secret_access_key": access_key["SecretAccessKey"],
    }


@pytest.fixture(scope="session")
def localstack_wrong_account_credentials() -> dict[str, str]:
    """Credentials that LocalStack community maps to a different account."""
    return {
        "aws_access_key_id": "111111111111",
        "aws_secret_access_key": "111111111111",
    }
