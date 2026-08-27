"""Shared fixtures for AzureAppConfigSource integration tests under
``tests/integration/sources/azure_app_config/``.

Uses the official Azure App Configuration emulator with anonymous auth enabled — no Azure
subscription or real credentials required. This sandbox has no Docker access, so the exact
anonymous-auth handshake (``NoopCredential`` accepted as-is vs. requiring some other shape
of token) is unconfirmed locally; if CI shows a different approach is needed, adjust
``NoopCredential``/how it's passed to ``AzureAppConfigurationClient`` in the test module.

The emulator only serves plain HTTP, but azure-core's ``BearerTokenCredentialPolicy`` refuses
non-HTTPS URLs by default. Every ``NoopCredential``-backed call (seeding via
``set_configuration_setting`` and reads via ``AzureAppConfigSource.request_options``) must pass
``enforce_https=False`` explicitly; the HMAC/connection-string path is unaffected since it uses a
different authentication policy.
"""

from collections.abc import Generator

import pytest
from testcontainers.core.container import DockerContainer

from tests.integration.sources.azure_app_config.helpers import (
    APP_CONFIG_INTERNAL_PORT,
    app_config_endpoint,
    start_app_config_container,
)


@pytest.fixture(scope="package")
def azure_app_config_container() -> Generator[DockerContainer]:
    """One App Configuration emulator container, anonymous auth enabled, shared for the run."""
    yield from start_app_config_container(APP_CONFIG_INTERNAL_PORT)


@pytest.fixture(scope="package")
def azure_app_config_endpoint(azure_app_config_container: DockerContainer) -> str:
    """Base HTTP URL of the running emulator, blocked until ``/health`` responds."""
    return app_config_endpoint(azure_app_config_container, APP_CONFIG_INTERNAL_PORT)
