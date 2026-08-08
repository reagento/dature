"""Shared fixtures for AwsSecretsManagerSource tests under ``tests/integration/sources/secrets_manager/``."""

import pytest


@pytest.fixture
def secrets_manager_client(localstack_container):
    return localstack_container.get_client("secretsmanager")


@pytest.fixture
def secrets_manager_endpoint_url(localstack_container) -> str:
    return str(localstack_container.get_url())


@pytest.fixture
def secrets_manager_region_name(localstack_container) -> str:
    return str(localstack_container.region_name)
