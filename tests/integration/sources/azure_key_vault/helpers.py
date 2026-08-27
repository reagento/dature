"""Shared, fixture-independent helpers for AzureKeyVaultSource integration tests.

Kept separate from ``conftest.py`` so both it and the test modules can import these
without going through pytest fixture injection.
"""

from collections.abc import Generator
from typing import Final

import requests
import urllib3
from testcontainers.core.container import DockerContainer

from tests.integration.waiting import retry_until_ready

LOWKEY_VAULT_IMAGE: Final = "nagyesta/lowkey-vault:2.7.4"
LOWKEY_VAULT_PORT: Final = 8443

# lowkey-vault serves a self-signed cert; suppress the resulting per-request warning noise.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def start_key_vault_container(port: int) -> Generator[DockerContainer]:
    """Start one lowkey-vault container, bound to a fixed host port, and yield it."""
    container = DockerContainer(LOWKEY_VAULT_IMAGE).with_bind_ports(port, port)
    with container as c:
        yield c


def key_vault_url(port: int) -> str:
    """The vault URL, blocked until lowkey-vault accepts HTTPS connections."""
    url = f"https://localhost:{port}"

    def _check_ready() -> None:
        requests.get(url, verify=False, timeout=5)  # noqa: S501

    retry_until_ready(_check_ready, ConnectionError, requests.exceptions.ConnectionError)
    return url
