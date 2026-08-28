"""Integration tests for ZookeeperSource — require a live ZooKeeper container via testcontainers.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

import json
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest
from kazoo.client import KazooClient
from kazoo.security import make_digest_acl
from testcontainers.core.container import DockerContainer

from dature import ZookeeperSource, configure, load
from dature.errors import DatureConfigError, SourceLocation
from dature.loading.merge_runtime import apply_source_config_group
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.integration.sources.zookeeper.helpers import (
    make_zk_client,
    start_zookeeper_container,
    zk_address,
)
from tests.sources.checker import assert_all_types_equal

KV_PREFIX: Final = "myapp"
ALL_TYPES_PREFIX: Final = "all_types"
EXPECTED_SECRET: Final = {"db_password": "s3cret", "port": "5432", "name": "myapp"}


@dataclass
class _Config:
    db_password: str
    port: int
    name: str


EXPECTED_DATACLASS: Final = _Config(db_password="s3cret", port=5432, name="myapp")


@pytest.fixture
def zk_address_no_auth(zk_container, zk_internal_port) -> tuple[str, int]:
    return zk_address(zk_container, zk_internal_port)


@pytest.fixture
def _kv_tree(zk_client: KazooClient) -> Generator[None]:
    """Write the canonical secret as a leaf znode per field, nested under KV_PREFIX."""
    for key, value in EXPECTED_SECRET.items():
        zk_client.create(f"/{KV_PREFIX}/{key}", value.encode("utf-8"), makepath=True)
    yield
    zk_client.delete(f"/{KV_PREFIX}", recursive=True)


@pytest.fixture
def _kv_json_doc(zk_client: KazooClient) -> Generator[None]:
    """Write the canonical secret as a single JSON document at KV_PREFIX."""
    zk_client.create(f"/{KV_PREFIX}", json.dumps(EXPECTED_SECRET).encode("utf-8"), makepath=True)
    yield
    zk_client.delete(f"/{KV_PREFIX}", recursive=True)


@pytest.fixture
def _kv_all_types(zk_client: KazooClient, all_types_zookeeper_kv_file: Path) -> Generator[None]:
    """Write every key of the all-types KV tree individually as znodes."""
    kv_map = json.loads(all_types_zookeeper_kv_file.read_text())
    for key, value in kv_map.items():
        zk_client.create(f"/{key}", value.encode("utf-8"), makepath=True)
    yield
    zk_client.delete(f"/{ALL_TYPES_PREFIX}", recursive=True)


@pytest.mark.usefixtures("_reset_config")
class TestZookeeperSourceRecursive:
    @pytest.mark.usefixtures("_kv_tree")
    def test_load_basic(self, zk_address_no_auth):
        zk_host, zk_port = zk_address_no_auth
        result = load(
            ZookeeperSource(hosts=f"{zk_host}:{zk_port}", path=KV_PREFIX),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS

    def test_missing_prefix_raises(self, zk_address_no_auth):
        zk_host, zk_port = zk_address_no_auth
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                ZookeeperSource(hosts=f"{zk_host}:{zk_port}", path="does/not/exist"),
                schema=_Config,
            )

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == f"Zookeeper znode not found: zk://{zk_host}:{zk_port}/does/not/exist"

    @pytest.mark.usefixtures("_kv_tree")
    def test_resolve_location_renders_real_value(self, zk_address_no_auth):
        zk_host, zk_port = zk_address_no_auth
        source = apply_source_config_group(
            ZookeeperSource(hosts=f"{zk_host}:{zk_port}", path=KV_PREFIX, expand_env_vars="default")
        )

        result = source.load_raw()
        locations = source.resolve_location(
            field_path=["db_password"], nested_conflict=None, loaded_data=result.loaded_data
        )

        assert locations == [
            SourceLocation(
                location_label="ZOOKEEPER",
                file_path=None,
                line_range=None,
                line_content=[
                    f"zk://{zk_host}:{zk_port}/{KV_PREFIX}: db_password = s3cret",
                ],
                env_var_name=None,
                line_carets=None,
            ),
        ]

    @pytest.mark.usefixtures("_kv_tree")
    def test_hosts_as_list(self, zk_address_no_auth):
        zk_host, zk_port = zk_address_no_auth
        result = load(
            ZookeeperSource(hosts=[f"{zk_host}:{zk_port}"], path=KV_PREFIX),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS

    @pytest.mark.usefixtures("_kv_tree")
    def test_non_recursive_reads_single_leaf_znode(self, zk_address_no_auth):
        # recursive=False reads exactly the one znode at `path` — its own data, keyed
        # under its last path segment — never descending into children.
        zk_host, zk_port = zk_address_no_auth

        @dataclass
        class Config:
            name: str

        result = load(
            ZookeeperSource(hosts=f"{zk_host}:{zk_port}", path=f"{KV_PREFIX}/name", recursive=False),
            schema=Config,
        )

        assert result == Config(name="myapp")


@pytest.mark.usefixtures("_reset_config")
class TestZookeeperSourceAllTypes:
    @pytest.mark.usefixtures("_kv_all_types")
    def test_comprehensive_type_conversion(self, zk_address_no_auth):
        zk_host, zk_port = zk_address_no_auth
        result = load(
            ZookeeperSource(hosts=f"{zk_host}:{zk_port}", path=ALL_TYPES_PREFIX),
            schema=AllPythonTypesCompact,
        )

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config", "_kv_json_doc")
class TestZookeeperSourceSingleNodeJson:
    def test_load_json_document_as_root(self, zk_address_no_auth):
        zk_host, zk_port = zk_address_no_auth
        result = load(
            ZookeeperSource(hosts=f"{zk_host}:{zk_port}", path=KV_PREFIX, recursive=False, decode="json"),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS


@pytest.mark.usefixtures("_reset_config")
class TestZookeeperSourceRawDecode:
    def test_raw_decode_yields_bytes(self, zk_client: KazooClient, zk_address_no_auth):
        zk_host, zk_port = zk_address_no_auth
        zk_client.create(f"/{KV_PREFIX}/blob", b"\x00\x01raw", makepath=True)

        @dataclass
        class Config:
            blob: bytes

        try:
            result = load(
                ZookeeperSource(hosts=f"{zk_host}:{zk_port}", path=KV_PREFIX, decode="raw"),
                schema=Config,
            )

            assert result == Config(blob=b"\x00\x01raw")
        finally:
            zk_client.delete(f"/{KV_PREFIX}", recursive=True)


@pytest.fixture(scope="class")
def _zk_auth_container(zk_internal_port: int) -> Generator[DockerContainer]:
    """A dedicated container for auth tests — its znodes carry restrictive digest ACLs that
    would break every other test relying on unauthenticated access to the shared container."""
    yield from start_zookeeper_container(zk_internal_port)


@pytest.fixture(scope="class")
def zk_address_auth(_zk_auth_container: DockerContainer, zk_internal_port: int) -> tuple[str, int]:
    return zk_address(_zk_auth_container, zk_internal_port)


@pytest.fixture(scope="class")
def _zk_auth_admin_client(
    _zk_auth_container: DockerContainer, zk_internal_port: int, zk_digest_user: str, zk_digest_password: str
) -> Generator[KazooClient]:
    """A client authenticated as the digest user, used to seed ACL-protected znodes."""
    client = make_zk_client(
        _zk_auth_container, zk_internal_port, auth_data=[("digest", f"{zk_digest_user}:{zk_digest_password}")]
    )
    yield client
    client.stop()
    client.close()


@pytest.mark.usefixtures("_reset_config")
class TestZookeeperSourceAuth:
    @pytest.fixture(autouse=True)
    def _seed_secret(self, _zk_auth_admin_client: KazooClient, zk_digest_user: str, zk_digest_password: str):
        acl = [make_digest_acl(zk_digest_user, zk_digest_password, read=True, write=True, admin=True)]
        _zk_auth_admin_client.create(f"/{KV_PREFIX}", makepath=True, acl=acl)
        for key, value in EXPECTED_SECRET.items():
            _zk_auth_admin_client.create(f"/{KV_PREFIX}/{key}", value.encode("utf-8"), acl=acl)
        yield
        _zk_auth_admin_client.delete(f"/{KV_PREFIX}", recursive=True)

    def test_correct_creds_load(self, zk_address_auth, zk_digest_user, zk_digest_password):
        zk_auth_host, zk_auth_port = zk_address_auth
        result = load(
            ZookeeperSource(
                hosts=f"{zk_auth_host}:{zk_auth_port}", path=KV_PREFIX, user=zk_digest_user, password=zk_digest_password
            ),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS

    def test_no_creds_raises_permission_error(self, zk_address_auth):
        zk_auth_host, zk_auth_port = zk_address_auth
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                ZookeeperSource(hosts=f"{zk_auth_host}:{zk_auth_port}", path=KV_PREFIX),
                schema=_Config,
            )

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, PermissionError)
        assert inner.args[0] == f"Zookeeper auth failed for zk://{zk_auth_host}:{zk_auth_port}/{KV_PREFIX}"

    def test_wrong_password_raises_permission_error(self, zk_address_auth, zk_digest_user):
        zk_auth_host, zk_auth_port = zk_address_auth
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                ZookeeperSource(
                    hosts=f"{zk_auth_host}:{zk_auth_port}", path=KV_PREFIX, user=zk_digest_user, password="wrong"
                ),
                schema=_Config,
            )

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, PermissionError)
        assert inner.args[0] == f"Zookeeper auth failed for zk://{zk_auth_host}:{zk_auth_port}/{KV_PREFIX}"


@pytest.mark.usefixtures("_reset_config", "_kv_tree")
class TestZookeeperSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="settings_from_configure"),
            pytest.param("env", id="settings_from_env"),
        ],
    )
    def test_load_with_settings(self, via, zk_address_no_auth, monkeypatch):
        zk_host, zk_port = zk_address_no_auth
        if via == "configure":
            configure(zookeeper={"hosts": f"{zk_host}:{zk_port}"})
        else:
            monkeypatch.setenv("DATURE_ZOOKEEPER__HOSTS", f"{zk_host}:{zk_port}")

        result = load(ZookeeperSource(path=KV_PREFIX), schema=_Config)

        assert result == EXPECTED_DATACLASS
