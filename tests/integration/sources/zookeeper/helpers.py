"""Shared, fixture-independent helpers for ZookeeperSource integration tests.

Kept separate from ``conftest.py`` so both it and the test modules can import these
without going through pytest fixture injection.
"""

from collections.abc import Generator
from typing import Final

from kazoo.client import KazooClient
from kazoo.exceptions import ConnectionLoss
from kazoo.handlers.threading import KazooTimeoutError
from testcontainers.core.container import DockerContainer

from tests.integration.waiting import retry_until_ready

ZOOKEEPER_IMAGE: Final = "zookeeper:3.9"
ZOOKEEPER_DIGEST_USER: Final = "root"
ZOOKEEPER_DIGEST_PASSWORD: Final = "test-root-password"


def start_zookeeper_container(internal_port: int) -> Generator[DockerContainer]:
    """Start one ZooKeeper container and yield it.

    Shared by the package-scoped (unauthenticated) and class-scoped (digest-ACL) container
    fixtures — each auth test writes its own restricted znodes, so it gets its own instance
    rather than mutating the ACLs every other test in the package relies on.
    """
    container = DockerContainer(ZOOKEEPER_IMAGE).with_exposed_ports(internal_port)
    with container as c:
        yield c


def zk_address(container: DockerContainer, internal_port: int) -> tuple[str, int]:
    """``(host, port)`` for reaching *container* from the test process."""
    return container.get_container_host_ip(), int(container.get_exposed_port(internal_port))


def make_zk_client(container: DockerContainer, internal_port: int, **kwargs: object) -> KazooClient:
    """A ``KazooClient`` pointed at *container*, blocked until it accepts a real write.

    The container's log lines are visible before the ZooKeeper server actually accepts
    client connections, so — as with the etcd/Consul fixtures — a live write is the only
    reliable readiness signal.
    """
    host, port = zk_address(container, internal_port)
    client = KazooClient(hosts=f"{host}:{port}", **kwargs)
    retry_until_ready(lambda: client.start(timeout=5), KazooTimeoutError)
    retry_until_ready(lambda: client.ensure_path("/_readiness"), ConnectionLoss)
    return client
