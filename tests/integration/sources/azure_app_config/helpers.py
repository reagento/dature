"""Shared, fixture-independent helpers for AzureAppConfigSource integration tests.

Kept separate from ``conftest.py`` so both it and the test modules can import these
without going through pytest fixture injection.
"""

from collections.abc import Generator
from typing import Final

import requests
from testcontainers.core.container import DockerContainer

from tests.integration.waiting import retry_until_ready

APP_CONFIG_IMAGE: Final = "mcr.microsoft.com/azure-app-configuration/app-configuration-emulator:1.2.0"
APP_CONFIG_INTERNAL_PORT: Final = 8483

HMAC_ACCESS_KEY_ID: Final = "emulator-test-id"
HMAC_ACCESS_KEY_SECRET: Final = "c2VjcmV0LWtleS12YWx1ZS1mb3ItaG1hYy1hdXRoLXRlc3Rz"
"""Base64-encoded — the SDK base64-decodes this to key the HMAC signature."""


def start_app_config_container(
    internal_port: int, *, anonymous: bool = True, hmac: bool = False
) -> Generator[DockerContainer]:
    """Start one App Configuration emulator container and yield it.

    Shared by the package-scoped (anonymous) and class-scoped (HMAC auth) container
    fixtures, which differ only in which auth scheme(s) get enabled.
    """
    container = DockerContainer(APP_CONFIG_IMAGE).with_exposed_ports(internal_port)
    if anonymous:
        container = container.with_env("Tenant:AnonymousAuthEnabled", "true").with_env(
            "Authentication:Anonymous:AnonymousUserRole", "Owner"
        )
    else:
        container = container.with_env("Tenant:AnonymousAuthEnabled", "false")
    if hmac:
        container = (
            container.with_env("Tenant:HmacSha256Enabled", "true")
            .with_env("Tenant:AccessKeys:0:Id", HMAC_ACCESS_KEY_ID)
            .with_env("Tenant:AccessKeys:0:Secret", HMAC_ACCESS_KEY_SECRET)
        )
    with container as c:
        yield c


def app_config_endpoint(container: DockerContainer, internal_port: int) -> str:
    """Base HTTP URL of *container*, blocked until ``/health`` responds."""
    host = container.get_container_host_ip()
    port = container.get_exposed_port(internal_port)
    endpoint = f"http://{host}:{port}"

    def _check_health() -> None:
        requests.get(f"{endpoint}/health", timeout=5).raise_for_status()

    retry_until_ready(_check_health, requests.exceptions.RequestException)
    return endpoint
