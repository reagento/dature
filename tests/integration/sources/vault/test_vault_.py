"""Integration tests for VaultSource — require a live Vault container via testcontainers.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast
from urllib.parse import urlparse

import hvac
import pytest

from dature import VaultSource, configure, load
from dature.errors import DatureConfigError, SourceLocation
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal

KV_PATH: Final = "myapp/config"
KV1_MOUNT: Final = "kv1"
ALL_TYPES_PATH: Final = "myapp/all_types"
EXPECTED_SECRET: Final = {"db_password": "s3cret", "port": "5432", "name": "myapp"}


@dataclass
class _Config:
    db_password: str
    port: int
    name: str


EXPECTED_DATACLASS: Final = _Config(db_password="s3cret", port=5432, name="myapp")


@pytest.fixture
def vault_url(vault_container) -> str:
    return cast("str", vault_container.get_connection_url())


@pytest.fixture
def vault_host(vault_url: str) -> str:
    return cast("str", urlparse(vault_url).hostname)


@pytest.fixture
def vault_port(vault_url: str) -> int:
    return cast("int", urlparse(vault_url).port)


@pytest.fixture
def vault_scheme(vault_url: str) -> str:
    return urlparse(vault_url).scheme


@pytest.fixture
def vault_root_token(vault_container) -> str:
    return cast("str", vault_container.root_token)


@pytest.fixture
def _kv2_secret(vault_client):
    """Write the canonical secret in the default KV v2 mount."""
    vault_client.secrets.kv.v2.create_or_update_secret(path=KV_PATH, secret=EXPECTED_SECRET)


@pytest.fixture
def _kv2_all_types(vault_client, all_types_vault_file: Path):
    """Write the all-types payload in the default KV v2 mount, as a single secret."""
    payload = json.loads(all_types_vault_file.read_text())
    vault_client.secrets.kv.v2.create_or_update_secret(path=ALL_TYPES_PATH, secret=payload)


@pytest.fixture
def _kv1_mount(vault_client):
    """Enable a KV v1 mount at ``KV1_MOUNT`` and write the canonical secret there."""
    with contextlib.suppress(hvac.exceptions.InvalidRequest):
        vault_client.sys.enable_secrets_engine(
            backend_type="kv",
            path=KV1_MOUNT,
            options={"version": "1"},
        )
    vault_client.secrets.kv.v1.create_or_update_secret(
        path=KV_PATH,
        secret=EXPECTED_SECRET,
        mount_point=KV1_MOUNT,
    )


@pytest.fixture
def approle_creds(vault_client):
    """Enable approle, create role 'tester' with read on secret/, return (role_id, secret_id)."""
    with contextlib.suppress(hvac.exceptions.InvalidRequest):
        vault_client.sys.enable_auth_method(method_type="approle")
    vault_client.sys.create_or_update_policy(
        name="reader",
        policy='path "secret/*" { capabilities = ["read"] }',
    )
    vault_client.auth.approle.create_or_update_approle(
        role_name="tester",
        token_policies=["reader"],
    )
    role_id = vault_client.auth.approle.read_role_id(role_name="tester")["data"]["role_id"]
    secret_id = vault_client.auth.approle.generate_secret_id(role_name="tester")["data"]["secret_id"]
    return role_id, secret_id


@pytest.mark.usefixtures("_reset_config")
class TestVaultSourceTokenKv2:
    @pytest.mark.usefixtures("_kv2_secret")
    def test_load_basic(self, vault_host, vault_port, vault_scheme, vault_root_token):
        result = load(
            VaultSource(host=vault_host, port=vault_port, scheme=vault_scheme, token=vault_root_token, path=KV_PATH),
            schema=_Config,
        )
        assert result == EXPECTED_DATACLASS

    def test_path_not_found_raises(self, vault_url, vault_host, vault_port, vault_scheme, vault_root_token):
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                VaultSource(
                    host=vault_host,
                    port=vault_port,
                    scheme=vault_scheme,
                    token=vault_root_token,
                    path="does/not/exist",
                ),
                schema=_Config,
            )
        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == f"Vault path not found: {vault_url}/v1/secret/data/does/not/exist"

    @pytest.mark.usefixtures("_kv2_secret")
    def test_invalid_token_raises(self, vault_url, vault_host, vault_port, vault_scheme):
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                VaultSource(host=vault_host, port=vault_port, scheme=vault_scheme, token="bad-token", path=KV_PATH),
                schema=_Config,
            )
        assert isinstance(exc_info.value.exceptions[0], PermissionError)
        assert exc_info.value.exceptions[0].args[0] == f"Vault auth failed for {vault_url}"

    @pytest.mark.usefixtures("_kv2_secret")
    def test_resolve_location_renders_real_value(
        self, vault_url, vault_host, vault_port, vault_scheme, vault_root_token
    ):
        source = VaultSource(
            host=vault_host,
            port=vault_port,
            scheme=vault_scheme,
            token=vault_root_token,
            path=KV_PATH,
            mount_point="secret",
            kv_version=2,
        )
        result = source.load_raw()
        locations = source.resolve_location(
            field_path=["db_password"], nested_conflict=None, loaded_data=result.loaded_data
        )
        assert locations == [
            SourceLocation(
                location_label="VAULT",
                file_path=None,
                line_range=None,
                line_content=[f"{vault_url}/v1/secret/data/{KV_PATH}: db_password = s3cret"],
                env_var_name=None,
                line_carets=None,
            ),
        ]


@pytest.mark.usefixtures("_reset_config")
class TestVaultSourceAllTypes:
    @pytest.mark.usefixtures("_kv2_all_types")
    def test_comprehensive_type_conversion(self, vault_host, vault_port, vault_scheme, vault_root_token):
        result = load(
            VaultSource(
                host=vault_host, port=vault_port, scheme=vault_scheme, token=vault_root_token, path=ALL_TYPES_PATH
            ),
            schema=AllPythonTypesCompact,
        )
        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config", "_kv1_mount")
class TestVaultSourceTokenKv1:
    def test_load_basic(self, vault_host, vault_port, vault_scheme, vault_root_token):
        result = load(
            VaultSource(
                host=vault_host,
                port=vault_port,
                scheme=vault_scheme,
                token=vault_root_token,
                path=KV_PATH,
                mount_point=KV1_MOUNT,
                kv_version=1,
            ),
            schema=_Config,
        )
        assert result == EXPECTED_DATACLASS

    def test_path_not_found_raises(self, vault_url, vault_host, vault_port, vault_scheme, vault_root_token):
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                VaultSource(
                    host=vault_host,
                    port=vault_port,
                    scheme=vault_scheme,
                    token=vault_root_token,
                    path="does/not/exist",
                    mount_point=KV1_MOUNT,
                    kv_version=1,
                ),
                schema=_Config,
            )
        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == f"Vault path not found: {vault_url}/v1/{KV1_MOUNT}/does/not/exist"


@pytest.mark.usefixtures("_reset_config", "_kv2_secret")
class TestVaultSourceAppRole:
    def test_login_and_read(self, vault_host, vault_port, vault_scheme, approle_creds):
        role_id, secret_id = approle_creds
        result = load(
            VaultSource(
                host=vault_host,
                port=vault_port,
                scheme=vault_scheme,
                role_id=role_id,
                secret_id=secret_id,
                path=KV_PATH,
            ),
            schema=_Config,
        )
        assert result == EXPECTED_DATACLASS

    def test_invalid_role_id_raises(self, vault_host, vault_port, vault_scheme, approle_creds):
        _, secret_id = approle_creds
        with pytest.raises(Exception):  # noqa: B017, PT011
            load(
                VaultSource(
                    host=vault_host,
                    port=vault_port,
                    scheme=vault_scheme,
                    role_id="invalid-role-id",
                    secret_id=secret_id,
                    path=KV_PATH,
                ),
                schema=_Config,
            )


@pytest.mark.usefixtures("_reset_config", "_kv2_secret")
class TestVaultSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="creds_from_configure"),
            pytest.param("env", id="creds_from_env"),
        ],
    )
    def test_load_with_creds(self, via, vault_host, vault_port, vault_scheme, vault_root_token, monkeypatch):
        if via == "configure":
            configure(vault={"host": vault_host, "port": vault_port, "scheme": vault_scheme, "token": vault_root_token})
        else:
            monkeypatch.setenv("DATURE_VAULT__HOST", vault_host)
            monkeypatch.setenv("DATURE_VAULT__PORT", str(vault_port))
            monkeypatch.setenv("DATURE_VAULT__SCHEME", vault_scheme)
            monkeypatch.setenv("DATURE_VAULT__TOKEN", vault_root_token)

        result = load(VaultSource(path=KV_PATH), schema=_Config)
        assert result == EXPECTED_DATACLASS
