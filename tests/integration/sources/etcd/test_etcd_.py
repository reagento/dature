"""Integration tests for EtcdSource — require a live etcd container via testcontainers.

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
from etcd3gw.client import Etcd3Client
from testcontainers.core.container import DockerContainer

from dature import EtcdSource, configure, load
from dature.errors import DatureConfigError, SourceLocation
from dature.loading.merge_runtime import apply_source_config_group
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.integration.sources.etcd.helpers import (
    etcd_address,
    make_etcd_client,
    start_etcd_container,
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
def etcd_address_no_auth(etcd_container, etcd_internal_port) -> tuple[str, int]:
    return etcd_address(etcd_container, etcd_internal_port)


@pytest.fixture
def _kv_tree(etcd_client: Etcd3Client):
    """Write the canonical secret as a flat key per field, nested under KV_PREFIX."""
    for key, value in EXPECTED_SECRET.items():
        etcd_client.put(f"{KV_PREFIX}/{key}", value)


@pytest.fixture
def _kv_json_doc(etcd_client: Etcd3Client):
    """Write the canonical secret as a single JSON document at KV_PREFIX."""
    etcd_client.put(KV_PREFIX, json.dumps(EXPECTED_SECRET))


@pytest.fixture
def _kv_all_types(etcd_client: Etcd3Client, all_types_etcd_kv_file: Path):
    """Write every key of the all-types KV tree individually."""
    kv_map = json.loads(all_types_etcd_kv_file.read_text())
    for key, value in kv_map.items():
        etcd_client.put(key, value)


@pytest.mark.usefixtures("_reset_config")
class TestEtcdSourceRecursive:
    @pytest.mark.usefixtures("_kv_tree")
    def test_load_basic(self, etcd_address_no_auth):
        etcd_host, etcd_port = etcd_address_no_auth
        result = load(
            EtcdSource(host=etcd_host, port=etcd_port, path=KV_PREFIX),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS

    def test_missing_prefix_raises(self, etcd_address_no_auth):
        etcd_host, etcd_port = etcd_address_no_auth
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                EtcdSource(host=etcd_host, port=etcd_port, path="does/not/exist"),
                schema=_Config,
            )

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == f"etcd key not found: http://{etcd_host}:{etcd_port}/v3/kv/does/not/exist"

    @pytest.mark.usefixtures("_kv_tree")
    def test_resolve_location_renders_real_value(self, etcd_address_no_auth):
        etcd_host, etcd_port = etcd_address_no_auth
        source = apply_source_config_group(EtcdSource(host=etcd_host, port=etcd_port, path=KV_PREFIX))

        result = source.load_raw()
        locations = source.resolve_location(
            field_path=["db_password"], nested_conflict=None, loaded_data=result.loaded_data
        )

        assert locations == [
            SourceLocation(
                location_label="ETCD",
                file_path=None,
                line_range=None,
                line_content=[
                    f"http://{etcd_host}:{etcd_port}/v3/kv/{KV_PREFIX}: db_password = s3cret",
                ],
                env_var_name=None,
                line_carets=None,
            ),
        ]


@pytest.mark.usefixtures("_reset_config")
class TestEtcdSourceAllTypes:
    @pytest.mark.usefixtures("_kv_all_types")
    def test_comprehensive_type_conversion(self, etcd_address_no_auth):
        etcd_host, etcd_port = etcd_address_no_auth
        result = load(
            EtcdSource(host=etcd_host, port=etcd_port, path=ALL_TYPES_PREFIX),
            schema=AllPythonTypesCompact,
        )

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config", "_kv_json_doc")
class TestEtcdSourceSingleKeyJson:
    def test_load_json_document_as_root(self, etcd_address_no_auth):
        etcd_host, etcd_port = etcd_address_no_auth
        result = load(
            EtcdSource(host=etcd_host, port=etcd_port, path=KV_PREFIX, recursive=False, decode="json"),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS


@pytest.mark.usefixtures("_reset_config")
class TestEtcdSourceRawDecode:
    def test_raw_decode_yields_bytes(self, etcd_client: Etcd3Client, etcd_address_no_auth):
        etcd_host, etcd_port = etcd_address_no_auth
        etcd_client.put(f"{KV_PREFIX}/blob", b"\x00\x01raw")

        @dataclass
        class Config:
            blob: bytes

        result = load(
            EtcdSource(host=etcd_host, port=etcd_port, path=KV_PREFIX, decode="raw"),
            schema=Config,
        )

        assert result == Config(blob=b"\x00\x01raw")


@pytest.fixture(scope="class")
def _etcd_auth_container(etcd_internal_port: int) -> Generator[DockerContainer]:
    """A dedicated container for auth tests — enabling RBAC on the shared package-scoped
    container would break every other test relying on unauthenticated access."""
    yield from start_etcd_container(etcd_internal_port)


@pytest.fixture(scope="class")
def _etcd_auth_client(_etcd_auth_container: DockerContainer, etcd_internal_port: int) -> Etcd3Client:
    return make_etcd_client(_etcd_auth_container, etcd_internal_port)


@pytest.fixture(scope="class")
def etcd_address_auth(_etcd_auth_container: DockerContainer, etcd_internal_port: int) -> tuple[str, int]:
    return etcd_address(_etcd_auth_container, etcd_internal_port)


@pytest.fixture(scope="class")
def _etcd_auth_enabled(
    _etcd_auth_container: DockerContainer, _etcd_auth_client: Etcd3Client, etcd_root_password: str
) -> None:
    """Create a root user/role and enable etcd RBAC auth, once for this container.

    etcd requires a user literally named ``root`` holding the ``root`` role before
    ``auth enable`` succeeds. Driving this through ``etcdctl`` (rather than raw
    gRPC-gateway JSON calls) sidesteps having to hand base64-encode the request bodies
    that ``Etcd3Client`` normally encodes for its own ``get``/``put``.
    """
    for args in (
        ("user", "add", f"root:{etcd_root_password}"),
        ("role", "add", "root"),
        ("user", "grant-role", "root", "root"),
        ("auth", "enable"),
    ):
        result = _etcd_auth_container.exec(["etcdctl", *args])
        assert result.exit_code == 0, result.output.decode()


@pytest.mark.usefixtures("_reset_config", "_etcd_auth_enabled")
class TestEtcdSourceAuth:
    @pytest.fixture(autouse=True)
    def _seed_secret(self, _etcd_auth_client: Etcd3Client, etcd_root_password: str):
        auth_client = _root_client(_etcd_auth_client, "root", etcd_root_password)

        for key, value in EXPECTED_SECRET.items():
            auth_client.put(f"{KV_PREFIX}/{key}", value)

    def test_correct_creds_load(self, etcd_address_auth, etcd_root_password):
        etcd_auth_host, etcd_auth_port = etcd_address_auth
        result = load(
            EtcdSource(
                host=etcd_auth_host, port=etcd_auth_port, path=KV_PREFIX, user="root", password=etcd_root_password
            ),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS

    def test_wrong_password_raises_permission_error(self, etcd_address_auth):
        etcd_auth_host, etcd_auth_port = etcd_address_auth
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                EtcdSource(host=etcd_auth_host, port=etcd_auth_port, path=KV_PREFIX, user="root", password="wrong"),
                schema=_Config,
            )

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, PermissionError)
        assert inner.args[0] == f"etcd auth failed for http://{etcd_auth_host}:{etcd_auth_port}/v3/kv/{KV_PREFIX}"

    def test_no_creds_raises_permission_error(self, etcd_address_auth):
        etcd_auth_host, etcd_auth_port = etcd_address_auth
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                EtcdSource(host=etcd_auth_host, port=etcd_auth_port, path=KV_PREFIX),
                schema=_Config,
            )

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, PermissionError)
        assert inner.args[0] == f"etcd auth failed for http://{etcd_auth_host}:{etcd_auth_port}/v3/kv/{KV_PREFIX}"


def _root_client(client: Etcd3Client, user: str, password: str) -> Etcd3Client:
    """A fresh, authenticated client — never mutate ``client`` itself, since it
    (``_etcd_auth_client``) is shared across the whole test class."""
    auth_client = Etcd3Client(host=client.host, port=client.port)
    resp = auth_client.post(
        auth_client.get_url("/auth/authenticate"),
        json={"name": user, "password": password},
    )
    auth_client.session.headers["Authorization"] = resp["token"]
    return auth_client


@pytest.mark.usefixtures("_reset_config", "_kv_tree")
class TestEtcdSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="settings_from_configure"),
            pytest.param("env", id="settings_from_env"),
        ],
    )
    def test_load_with_settings(self, via, etcd_address_no_auth, monkeypatch):
        etcd_host, etcd_port = etcd_address_no_auth
        if via == "configure":
            configure(etcd={"host": etcd_host, "port": etcd_port})
        else:
            monkeypatch.setenv("DATURE_ETCD__HOST", etcd_host)
            monkeypatch.setenv("DATURE_ETCD__PORT", str(etcd_port))

        result = load(EtcdSource(path=KV_PREFIX), schema=_Config)

        assert result == EXPECTED_DATACLASS
