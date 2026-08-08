"""Shared fixtures for AwsSecretsManagerSource tests under ``tests/integration/sources/secrets_manager/``."""

from collections.abc import Callable

import pytest
from botocore.exceptions import ClientError


@pytest.fixture(scope="session")
def secrets_manager_client(localstack_container):
    return localstack_container.get_client("secretsmanager")


@pytest.fixture(scope="session")
def secrets_manager_put_secret(secrets_manager_client) -> Callable[..., None]:
    def _put_secret(*, name: str, secret_string: str) -> None:
        try:
            secrets_manager_client.create_secret(Name=name, SecretString=secret_string)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ResourceExistsException":
                raise
            secrets_manager_client.put_secret_value(SecretId=name, SecretString=secret_string)

    return _put_secret


@pytest.fixture(scope="session")
def secrets_manager_endpoint_url(localstack_container) -> str:
    return str(localstack_container.get_url())


@pytest.fixture(scope="session")
def secrets_manager_region_name(localstack_container) -> str:
    return str(localstack_container.region_name)
