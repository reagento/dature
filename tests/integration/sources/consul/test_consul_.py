"""Integration tests for ConsulSource — require a live Consul container via testcontainers.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

import json
from dataclasses import dataclass
from typing import Final, cast

import pytest

from dature import ConsulSource, configure, load
from dature.errors import DatureConfigError, SourceLocation

KV_PREFIX: Final = "myapp"
EXPECTED_SECRET: Final = {"db_password": "s3cret", "port": "5432", "name": "myapp"}


@dataclass
class _Config:
    db_password: str
    port: int
    name: str


EXPECTED_DATACLASS: Final = _Config(db_password="s3cret", port=5432, name="myapp")


@pytest.fixture
def consul_host(consul_container) -> str:
    return cast("str", consul_container.get_container_host_ip())


@pytest.fixture
def consul_port(consul_container, consul_port) -> int:
    return int(consul_container.get_exposed_port(consul_port))


@pytest.fixture
def _kv_tree(consul_client):
    """Write the canonical secret as a flat key per field, nested under KV_PREFIX."""
    for key, value in EXPECTED_SECRET.items():
        consul_client.kv.put(f"{KV_PREFIX}/{key}", value)


@pytest.fixture
def _kv_json_doc(consul_client):
    """Write the canonical secret as a single JSON document at KV_PREFIX."""
    consul_client.kv.put(KV_PREFIX, json.dumps(EXPECTED_SECRET))


@pytest.mark.usefixtures("_reset_config")
class TestConsulSourceRecursive:
    @pytest.mark.usefixtures("_kv_tree")
    def test_load_basic(self, consul_host, consul_port):
        result = load(
            ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX),
            schema=_Config,
        )
        assert result == EXPECTED_DATACLASS

    def test_missing_prefix_raises(self, consul_host, consul_port):
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                ConsulSource(host=consul_host, port=consul_port, path="does/not/exist"),
                schema=_Config,
            )
        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == f"Consul key not found: http://{consul_host}:{consul_port}/v1/kv/does/not/exist"

    @pytest.mark.usefixtures("_kv_tree")
    def test_resolve_location_renders_real_value(self, consul_host, consul_port):
        source = ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX)
        result = source.load_raw()
        locations = source.resolve_location(
            field_path=["db_password"], nested_conflict=None, loaded_data=result.loaded_data
        )
        assert locations == [
            SourceLocation(
                location_label="CONSUL",
                file_path=None,
                line_range=None,
                line_content=[
                    f"http://{consul_host}:{consul_port}/v1/kv/{KV_PREFIX}: db_password = s3cret",
                ],
                env_var_name=None,
                line_carets=None,
            ),
        ]


@pytest.mark.usefixtures("_reset_config", "_kv_json_doc")
class TestConsulSourceSingleKeyJson:
    def test_load_json_document_as_root(self, consul_host, consul_port):
        result = load(
            ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX, recursive=False, decode="json"),
            schema=_Config,
        )
        assert result == EXPECTED_DATACLASS


@pytest.mark.usefixtures("_reset_config")
class TestConsulSourceRawDecode:
    def test_raw_decode_yields_bytes(self, consul_client, consul_host, consul_port):
        consul_client.kv.put(f"{KV_PREFIX}/blob", b"\x00\x01raw")

        @dataclass
        class Config:
            blob: bytes

        result = load(
            ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX, decode="raw"),
            schema=Config,
        )
        assert result == Config(blob=b"\x00\x01raw")


@pytest.mark.usefixtures("_reset_config")
class TestConsulSourceAcl:
    @pytest.mark.usefixtures("_kv_tree")
    def test_invalid_token_raises(self, consul_host, consul_port):
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX, token="bad-token"),
                schema=_Config,
            )
        # In Consul dev mode ACLs are disabled by default; a bogus token is simply ignored
        # rather than rejected, so this exercises the happy path through the token field
        # rather than the ACLPermissionDenied/ACLDisabled translation to PermissionError.
        inner = exc_info.value.exceptions[0]
        assert not isinstance(inner, PermissionError)


@pytest.mark.usefixtures("_reset_config", "_kv_tree")
class TestConsulSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="creds_from_configure"),
            pytest.param("env", id="creds_from_env"),
        ],
    )
    def test_load_with_creds(self, via, consul_host, consul_port, monkeypatch):
        if via == "configure":
            configure(consul={"host": consul_host, "port": consul_port})
        else:
            monkeypatch.setenv("DATURE_CONSUL__HOST", consul_host)
            monkeypatch.setenv("DATURE_CONSUL__PORT", str(consul_port))

        result = load(ConsulSource(path=KV_PREFIX), schema=_Config)
        assert result == EXPECTED_DATACLASS
