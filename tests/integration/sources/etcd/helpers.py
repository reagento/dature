"""Shared, fixture-independent helpers for EtcdSource integration tests.

Kept separate from ``conftest.py`` so both it and the test modules can import these
without going through pytest fixture injection.
"""

from collections.abc import Generator
from typing import Final

import requests.exceptions
from etcd3gw.client import Etcd3Client
from etcd3gw.exceptions import Etcd3Exception
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_container_is_ready

ETCD_IMAGE: Final = "gcr.io/etcd-development/etcd:v3.5.17"
ETCD_ROOT_PASSWORD: Final = "test-root-password"
ETCD_COMMAND: Final = "etcd --advertise-client-urls http://0.0.0.0:2379 --listen-client-urls http://0.0.0.0:2379"


def start_etcd_container(internal_port: int) -> Generator[DockerContainer]:
    """Start one etcd v3 container and yield it.

    Shared by the package-scoped (unauthenticated) and class-scoped (auth) container
    fixtures, which differ only in scope and in whether RBAC gets enabled afterwards —
    enabling RBAC is irreversible for a running container, so the auth test class needs
    its own instance rather than sharing the one every other test reads from.
    """
    container = DockerContainer(ETCD_IMAGE).with_command(ETCD_COMMAND).with_exposed_ports(internal_port)
    with container as c:
        yield c


@wait_container_is_ready(Etcd3Exception, ConnectionError, requests.exceptions.ConnectionError)
def wait_etcd_ready(client: Etcd3Client) -> None:
    """Block until *client* can perform a real KV write.

    The container's log lines are visible before its HTTP listener actually accepts
    connections, so — as with the Consul fixtures — a live write is the only reliable
    readiness signal.
    """
    client.put("_readiness", "ok")


def etcd_address(container: DockerContainer, internal_port: int) -> tuple[str, int]:
    """``(host, port)`` for reaching *container* from the test process."""
    return container.get_container_host_ip(), int(container.get_exposed_port(internal_port))


def make_etcd_client(container: DockerContainer, internal_port: int) -> Etcd3Client:
    """An ``Etcd3Client`` pointed at *container*, blocked until it accepts a real write."""
    host, port = etcd_address(container, internal_port)
    client = Etcd3Client(host=host, port=port)
    wait_etcd_ready(client)
    return client
