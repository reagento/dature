"""Shared fixtures for AwsSsmSource integration tests under ``tests/integration/sources/ssm/``."""

import pytest


@pytest.fixture
def ssm_client(localstack_container):
    return localstack_container.get_client("ssm")


@pytest.fixture
def ssm_endpoint_url(localstack_container) -> str:
    return str(localstack_container.get_url())


@pytest.fixture
def ssm_region_name(localstack_container) -> str:
    return str(localstack_container.region_name)
