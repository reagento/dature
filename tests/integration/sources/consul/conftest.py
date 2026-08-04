"""Shared fixtures for ConsulSource integration tests under ``tests/integration/sources/consul/``."""

import json
from collections.abc import Generator
from typing import Final

import consul.std
import pytest
from consul.exceptions import ConsulException
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_container_is_ready

CONSUL_IMAGE = "hashicorp/consul:1.18"
CONSUL_MGMT_TOKEN: Final = "test-mgmt-token"
_CONSUL_LOCAL_CONFIG: Final = json.dumps(
    {
        "acl": {
            "enabled": True,
            "default_policy": "deny",
            "down_policy": "extend-cache",
            "tokens": {"initial_management": CONSUL_MGMT_TOKEN, "agent": CONSUL_MGMT_TOKEN},
        },
    }
)


@pytest.fixture(scope="package")
def consul_internal_port() -> int:
    """The port that the Consul container is listening on (inside the container)."""
    return 8500


@pytest.fixture(scope="package")
def consul_container(consul_internal_port) -> Generator[DockerContainer]:
    """One Consul dev-mode container, ACLs enabled (default_policy=deny), shared by every
    test under sources/consul/ for the run."""
    container = (
        DockerContainer(CONSUL_IMAGE)
        .with_command("agent -dev -client=0.0.0.0")
        .with_env("CONSUL_LOCAL_CONFIG", _CONSUL_LOCAL_CONFIG)
        .with_exposed_ports(consul_internal_port)
    )
    with container as c:
        yield c


@pytest.fixture(scope="package")
def consul_token() -> str:
    return CONSUL_MGMT_TOKEN


@wait_container_is_ready(ConsulException, ConnectionError)
def _wait_acl_ready(client: consul.std.Consul) -> None:
    """Block until *client* can perform a real, token-authenticated KV write.

    "Synced node info" (the previous log-line wait) is logged before the ACL subsystem
    finishes initializing, so it isn't a reliable readiness signal once ACLs are enabled.
    A live write is: it fails with ConsulException until the token is actually honored.
    """
    client.kv.put("_readiness", "ok")


@pytest.fixture(scope="package")
def consul_client(consul_container: DockerContainer, consul_internal_port, consul_token: str) -> consul.std.Consul:
    """``consul.Consul`` client pointed at the running container, authenticated with the
    management token."""
    host = consul_container.get_container_host_ip()
    port = int(consul_container.get_exposed_port(consul_internal_port))
    client = consul.std.Consul(host=host, port=port, token=consul_token)
    _wait_acl_ready(client)
    return client
