"""Shared fixtures for integration tests under ``tests/integration/sources/``."""

from collections.abc import Generator

import pytest
from testcontainers.vault import VaultContainer

VAULT_IMAGE = "hashicorp/vault:1.16.1"  # ``latest`` is a moving target and has broken CI in the past


@pytest.fixture(scope="package")
def vault_container() -> Generator[VaultContainer]:
    """One Vault container shared by every test under sources/ for the run."""
    with VaultContainer(VAULT_IMAGE) as c:
        yield c
