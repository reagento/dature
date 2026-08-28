"""Shared fixtures for ZookeeperSource integration tests under ``tests/integration/sources/zookeeper/``."""

from collections.abc import Generator

import pytest
from kazoo.client import KazooClient
from testcontainers.core.container import DockerContainer

from tests.integration.sources.zookeeper.helpers import (
    ZOOKEEPER_DIGEST_PASSWORD,
    ZOOKEEPER_DIGEST_USER,
    make_zk_client,
    start_zookeeper_container,
)


@pytest.fixture(scope="package")
def zk_internal_port() -> int:
    """The port a ZooKeeper container listens on for client connections (inside the container)."""
    return 2181


@pytest.fixture(scope="package")
def zk_container(zk_internal_port) -> Generator[DockerContainer]:
    """One ZooKeeper container, unauthenticated, shared by every test under sources/zookeeper/."""
    yield from start_zookeeper_container(zk_internal_port)


@pytest.fixture(scope="package")
def zk_client(zk_container: DockerContainer, zk_internal_port: int) -> Generator[KazooClient]:
    """``KazooClient`` pointed at the running (unauthenticated) container."""
    client = make_zk_client(zk_container, zk_internal_port)
    yield client
    client.stop()
    client.close()


@pytest.fixture(scope="package")
def zk_digest_user() -> str:
    return ZOOKEEPER_DIGEST_USER


@pytest.fixture(scope="package")
def zk_digest_password() -> str:
    return ZOOKEEPER_DIGEST_PASSWORD
