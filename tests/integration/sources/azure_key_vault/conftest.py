"""Shared fixtures for AzureKeyVaultSource integration tests under
``tests/integration/sources/azure_key_vault/``.

Uses ``nagyesta/lowkey-vault`` (a third-party Key Vault test double — there is no official
Microsoft emulator) over HTTPS with a self-signed certificate, following the setup from the
official example at https://github.com/nagyesta/lowkey-vault-example-python:
``NoopCredential`` + ``verify_challenge_resource=False`` + a non-verifying transport.

This sandbox has no Docker access, so none of this has been exercised against a running
container locally. The container is bound to a fixed host port (rather than testcontainers'
usual random port) specifically to sidestep lowkey-vault's vault-alias-by-URI requirement
(see the plan doc) — if CI shows the alias still needs configuring via ``LOWKEY_VAULT_ALIASES``,
add that env var here.
"""

from collections.abc import Generator

import pytest
from azure.core.pipeline.transport import RequestsTransport
from testcontainers.core.container import DockerContainer

from tests.integration.sources.azure_key_vault.helpers import (
    LOWKEY_VAULT_PORT,
    key_vault_url,
    start_key_vault_container,
)


@pytest.fixture
def azure_key_vault_container() -> Generator[DockerContainer]:
    """A fresh lowkey-vault container per test, bound to a fixed host port.

    AzureKeyVaultSource's list mode (``name="*"``) enumerates *every* secret in the vault —
    there's no server-side prefix filter like Consul/SSM have — so a container shared across
    tests would leak secrets from one test into another's "list all" assertions. A dedicated
    container per test trades startup cost for correctness here.
    """
    yield from start_key_vault_container(LOWKEY_VAULT_PORT)


@pytest.fixture
def azure_key_vault_url(azure_key_vault_container: DockerContainer) -> str:  # noqa: ARG001
    """The vault URL, blocked until lowkey-vault accepts HTTPS connections."""
    return key_vault_url(LOWKEY_VAULT_PORT)


@pytest.fixture(scope="package")
def azure_key_vault_client_options() -> dict[str, object]:
    return {
        "verify_challenge_resource": False,
        "transport": RequestsTransport(connection_verify=False),
        "api_version": "7.6",
    }
