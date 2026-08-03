"""Shared fixtures for VaultSource integration tests under ``tests/integration/sources/vault/``."""

from collections.abc import Generator

import hvac
import pytest
from testcontainers.vault import VaultContainer

VAULT_IMAGE = "hashicorp/vault:1.16.1"  # ``latest`` is a moving target and has broken CI in the past


@pytest.fixture(scope="package")
def vault_container() -> Generator[VaultContainer]:
    """One Vault container shared by every test under sources/ for the run."""
    with VaultContainer(VAULT_IMAGE) as c:
        yield c


@pytest.fixture(scope="package")
def vault_client(vault_container: VaultContainer) -> hvac.Client:
    """Authenticated hvac.Client for the running container."""
    return hvac.Client(url=vault_container.get_connection_url(), token=vault_container.root_token)
