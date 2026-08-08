"""Shared fixtures for EtcdSource integration tests under ``tests/integration/sources/etcd/``."""

from collections.abc import Generator

import pytest
from etcd3gw.client import Etcd3Client
from testcontainers.core.container import DockerContainer

from tests.integration.sources.etcd.helpers import ETCD_ROOT_PASSWORD, make_etcd_client, start_etcd_container


@pytest.fixture(scope="package")
def etcd_internal_port() -> int:
    """The port that an etcd container is listening on (inside the container)."""
    return 2379


@pytest.fixture(scope="package")
def etcd_container(etcd_internal_port) -> Generator[DockerContainer]:
    """One etcd v3 container, unauthenticated, shared by every test under sources/etcd/."""
    yield from start_etcd_container(etcd_internal_port)


@pytest.fixture(scope="package")
def etcd_client(etcd_container: DockerContainer, etcd_internal_port: int) -> Etcd3Client:
    """``Etcd3Client`` pointed at the running (unauthenticated) container."""
    return make_etcd_client(etcd_container, etcd_internal_port)


@pytest.fixture(scope="package")
def etcd_root_password() -> str:
    return ETCD_ROOT_PASSWORD
