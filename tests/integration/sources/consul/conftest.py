"""Shared fixtures for ConsulSource integration tests under ``tests/integration/sources/consul/``."""

from collections.abc import Generator

import consul.std
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

CONSUL_IMAGE = "hashicorp/consul:1.18"


@pytest.fixture(scope="package")
def consul_port() -> int:
    """The port that the Consul container is listening on."""
    return 8500


@pytest.fixture(scope="package")
def consul_container(consul_port) -> Generator[DockerContainer]:
    """One Consul dev-mode container shared by every test under sources/consul/ for the run."""
    container = DockerContainer(CONSUL_IMAGE).with_command("agent -dev -client=0.0.0.0").with_exposed_ports(consul_port)
    with container as c:
        wait_for_logs(c, "Synced node info")
        yield c


@pytest.fixture(scope="package")
def consul_client(consul_container: DockerContainer, consul_port) -> consul.std.Consul:
    """``consul.Consul`` client pointed at the running container."""
    host = consul_container.get_container_host_ip()
    port = int(consul_container.get_exposed_port(consul_port))
    return consul.std.Consul(host=host, port=port)
