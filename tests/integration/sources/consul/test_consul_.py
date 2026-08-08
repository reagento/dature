"""Integration tests for ConsulSource — require a live Consul container via testcontainers.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import pytest

from dature import ConsulSource, configure, load
from dature.errors import DatureConfigError, SourceLocation
from dature.loading.merge_runtime import apply_source_config_group
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
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
def consul_host(consul_container) -> str:
    return cast("str", consul_container.get_container_host_ip())


@pytest.fixture
def consul_port(consul_container, consul_internal_port) -> int:
    return int(consul_container.get_exposed_port(consul_internal_port))


@pytest.fixture(autouse=True)
def _no_consul_http_token_env(monkeypatch):
    # CONSUL_HTTP_TOKEN silently overrides an explicitly-passed token (consul/base.py), which
    # would let a "no token" test case pass for the wrong reason.
    monkeypatch.delenv("CONSUL_HTTP_TOKEN", raising=False)


@pytest.fixture
def _kv_tree(consul_client):
    """Write the canonical secret as a flat key per field, nested under KV_PREFIX."""
    for key, value in EXPECTED_SECRET.items():
        consul_client.kv.put(f"{KV_PREFIX}/{key}", value)


@pytest.fixture
def _kv_json_doc(consul_client):
    """Write the canonical secret as a single JSON document at KV_PREFIX."""
    consul_client.kv.put(KV_PREFIX, json.dumps(EXPECTED_SECRET))


@pytest.fixture
def _kv_all_types(consul_client, all_types_consul_kv_file: Path):
    """Write every key of the all-types KV tree individually."""
    kv_map = json.loads(all_types_consul_kv_file.read_text())
    for key, value in kv_map.items():
        consul_client.kv.put(key, value)


@pytest.mark.usefixtures("_reset_config")
class TestConsulSourceRecursive:
    @pytest.mark.usefixtures("_kv_tree")
    def test_load_basic(self, consul_host, consul_port, consul_token):
        result = load(
            ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX, token=consul_token),
            schema=_Config,
        )
        assert result == EXPECTED_DATACLASS

    def test_missing_prefix_raises(self, consul_host, consul_port, consul_token):
        # A wrong-but-authenticated path still 404s: the management token reads anything, so
        # this stays a not-found case rather than an ACL denial (ACL is checked first in
        # _fetch, but the token here is valid — it's the path that doesn't exist).
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                ConsulSource(host=consul_host, port=consul_port, path="does/not/exist", token=consul_token),
                schema=_Config,
            )
        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == f"Consul key not found: http://{consul_host}:{consul_port}/v1/kv/does/not/exist"

    @pytest.mark.usefixtures("_kv_tree")
    def test_resolve_location_renders_real_value(self, consul_host, consul_port, consul_token):
        source = apply_source_config_group(
            ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX, token=consul_token)
        )
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


@pytest.mark.usefixtures("_reset_config")
class TestConsulSourceAllTypes:
    @pytest.mark.usefixtures("_kv_all_types")
    def test_comprehensive_type_conversion(self, consul_host, consul_port, consul_token):
        result = load(
            ConsulSource(host=consul_host, port=consul_port, path=ALL_TYPES_PREFIX, token=consul_token),
            schema=AllPythonTypesCompact,
        )
        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config", "_kv_json_doc")
class TestConsulSourceSingleKeyJson:
    def test_load_json_document_as_root(self, consul_host, consul_port, consul_token):
        result = load(
            ConsulSource(
                host=consul_host, port=consul_port, path=KV_PREFIX, recursive=False, decode="json", token=consul_token
            ),
            schema=_Config,
        )
        assert result == EXPECTED_DATACLASS


@pytest.mark.usefixtures("_reset_config")
class TestConsulSourceRawDecode:
    def test_raw_decode_yields_bytes(self, consul_client, consul_host, consul_port, consul_token):
        consul_client.kv.put(f"{KV_PREFIX}/blob", b"\x00\x01raw")

        @dataclass
        class Config:
            blob: bytes

        result = load(
            ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX, decode="raw", token=consul_token),
            schema=Config,
        )
        assert result == Config(blob=b"\x00\x01raw")


@pytest.mark.usefixtures("_reset_config")
class TestConsulSourceAcl:
    @pytest.mark.usefixtures("_kv_tree")
    def test_no_token_yields_not_found(self, consul_host, consul_port):
        # The anonymous token has no policies attached (default_policy=deny), and for a
        # *recursive* read Consul silently filters out keys the token can't see rather than
        # 403ing the whole request — so this surfaces as "key not found", not a permission error.
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX, token=None),
                schema=_Config,
            )
        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == f"Consul key not found: http://{consul_host}:{consul_port}/v1/kv/{KV_PREFIX}"

    @pytest.mark.usefixtures("_kv_tree")
    def test_bad_token_raises_permission_error(self, consul_host, consul_port):
        # A token that doesn't exist at all fails identification itself, which Consul 403s
        # outright — unlike the anonymous-token case above, this is a real ACLPermissionDenied.
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                ConsulSource(host=consul_host, port=consul_port, path=KV_PREFIX, token="bogus-token"),
                schema=_Config,
            )
        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, PermissionError)
        assert inner.args[0] == f"Consul auth failed for http://{consul_host}:{consul_port}/v1/kv/{KV_PREFIX}"


@pytest.mark.usefixtures("_reset_config", "_kv_tree")
class TestConsulSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="creds_from_configure"),
            pytest.param("env", id="creds_from_env"),
        ],
    )
    def test_load_with_creds(self, via, consul_host, consul_port, consul_token, monkeypatch):
        if via == "configure":
            configure(consul={"host": consul_host, "port": consul_port, "token": consul_token})
        else:
            monkeypatch.setenv("DATURE_CONSUL__HOST", consul_host)
            monkeypatch.setenv("DATURE_CONSUL__PORT", str(consul_port))
            monkeypatch.setenv("DATURE_CONSUL__TOKEN", consul_token)

        result = load(ConsulSource(path=KV_PREFIX), schema=_Config)
        assert result == EXPECTED_DATACLASS
