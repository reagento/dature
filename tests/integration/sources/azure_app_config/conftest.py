"""Shared fixtures for AzureAppConfigSource integration tests under
``tests/integration/sources/azure_app_config/``.

Uses the official Azure App Configuration emulator, confirmed on CI (Docker isn't available in
this sandbox) to require HMAC auth for any test that expects a successful load — anonymous auth
being enabled does *not* mean a ``TokenCredential``-backed (bearer) request succeeds: the emulator
401s any request carrying an ``Authorization: Bearer`` header, including the dummy token from
``NoopCredential``, rather than falling back to anonymous. So the shared container also enables
HMAC, and tests that need data to actually load authenticate via HMAC connection string.
``NoopCredential`` + ``endpoint=`` is kept only for the negative case (auth correctly rejected).

The emulator also only serves plain HTTP, and azure-core's ``BearerTokenCredentialPolicy`` refuses
non-HTTPS URLs by default. The remaining ``NoopCredential``-backed calls must pass
``enforce_https=False`` explicitly via ``AzureAppConfigSource.request_options``; the HMAC/
connection-string path is unaffected since it uses a different authentication policy.
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
    """One App Configuration emulator container, anonymous auth *and* HMAC enabled, shared for
    the run.

    HMAC is required here even though anonymous auth is on: the emulator 401s any request that
    carries an ``Authorization: Bearer`` header — including a dummy one from ``NoopCredential`` —
    rather than falling back to anonymous, so tests that need a successful load authenticate via
    HMAC connection string instead.
    """
    yield from start_app_config_container(APP_CONFIG_INTERNAL_PORT, hmac=True)


@pytest.fixture(scope="package")
def azure_app_config_endpoint(azure_app_config_container: DockerContainer) -> str:
    """Base HTTP URL of the running emulator, blocked until ``/health`` responds."""
    return app_config_endpoint(azure_app_config_container, APP_CONFIG_INTERNAL_PORT)
