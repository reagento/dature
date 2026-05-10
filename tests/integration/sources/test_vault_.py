"""Integration tests for VaultSource — require a live Vault container via testcontainers.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

import contextlib
from dataclasses import dataclass
from typing import Final, cast

import hvac
import pytest

from dature import VaultSource, configure, load
from dature.errors import SourceLocation

KV2_PATH: Final = "myapp/config"
KV1_PATH: Final = "myapp/config"
KV1_MOUNT: Final = "kv1"


@pytest.fixture
def vault_url(vault_container) -> str:
    return cast("str", vault_container.get_connection_url())


@pytest.fixture
def vault_root_token(vault_container) -> str:
    return cast("str", vault_container.get_root_token())


@pytest.fixture
def kv2_secret(vault_container):
    """Write a fixed secret in the default KV v2 mount."""
    client = vault_container.get_client()
    expected = {"db_password": "s3cret", "port": "5432", "name": "myapp"}
    client.secrets.kv.v2.create_or_update_secret(path=KV2_PATH, secret=expected)
    return expected


@pytest.fixture
def kv1_mount(vault_container):
    """Enable a KV v1 mount at kv1/ and write a secret there."""
    client = vault_container.get_client()
    with contextlib.suppress(hvac.exceptions.InvalidRequest):
        client.sys.enable_secrets_engine(
            backend_type="kv",
            path=KV1_MOUNT,
            options={"version": "1"},
        )
    expected = {"db_password": "v1-secret", "port": "5432"}
    client.secrets.kv.v1.create_or_update_secret(
        path=KV1_PATH,
        secret=expected,
        mount_point=KV1_MOUNT,
    )
    return KV1_MOUNT, expected


@pytest.fixture
def approle_creds(vault_container):
    """Enable approle, create role 'tester' with read on secret/, return (role_id, secret_id)."""
    client = vault_container.get_client()
    with contextlib.suppress(hvac.exceptions.InvalidRequest):
        client.sys.enable_auth_method(method_type="approle")
    client.sys.create_or_update_policy(
        name="reader",
        policy='path "secret/*" { capabilities = ["read"] }',
    )
    client.auth.approle.create_or_update_approle(
        role_name="tester",
        token_policies=["reader"],
    )
    role_id = client.auth.approle.read_role_id(role_name="tester")["data"]["role_id"]
    secret_id = client.auth.approle.generate_secret_id(role_name="tester")["data"]["secret_id"]
    return role_id, secret_id


@pytest.mark.usefixtures("_reset_config")
class TestVaultSourceTokenKv2:
    def test_load_basic(self, vault_url, vault_root_token, kv2_secret):
        source = VaultSource(url=vault_url, token=vault_root_token, path=KV2_PATH)
        assert source.load_raw().data == kv2_secret

    @pytest.mark.usefixtures("kv2_secret")
    def test_load_into_dataclass(self, vault_url, vault_root_token):
        @dataclass
        class Config:
            db_password: str
            port: int
            name: str

        result = load(
            VaultSource(url=vault_url, token=vault_root_token, path=KV2_PATH),
            schema=Config,
        )
        assert result == Config(db_password="s3cret", port=5432, name="myapp")

    def test_path_not_found_raises(self, vault_url, vault_root_token):
        source = VaultSource(url=vault_url, token=vault_root_token, path="does/not/exist")
        with pytest.raises(KeyError, match="Vault path not found"):
            source.load_raw()

    @pytest.mark.usefixtures("kv2_secret")
    def test_invalid_token_raises(self, vault_url):
        source = VaultSource(url=vault_url, token="bad-token", path=KV2_PATH)
        with pytest.raises((PermissionError, hvac.exceptions.Forbidden, hvac.exceptions.Unauthorized)):
            source.load_raw()

    @pytest.mark.usefixtures("kv2_secret")
    def test_resolve_location_renders_real_value(self, vault_url, vault_root_token):
        source = VaultSource(
            url=vault_url,
            token=vault_root_token,
            path=KV2_PATH,
            mount_point="secret",
            kv_version=2,
        )
        source.load_raw()
        locations = source.resolve_location(field_path=["db_password"], file_content=None, nested_conflict=None)
        assert locations == [
            SourceLocation(
                location_label="VAULT",
                file_path=None,
                line_range=None,
                line_content=[f"{vault_url}/v1/secret/data/{KV2_PATH}: db_password = s3cret"],
                env_var_name=None,
                line_carets=None,
            ),
        ]


@pytest.mark.usefixtures("_reset_config")
class TestVaultSourceTokenKv1:
    def test_load_basic(self, vault_url, vault_root_token, kv1_mount):
        mount, expected = kv1_mount
        source = VaultSource(
            url=vault_url,
            token=vault_root_token,
            path=KV1_PATH,
            mount_point=mount,
            kv_version=1,
        )
        assert source.load_raw().data == expected

    def test_path_not_found_raises(self, vault_url, vault_root_token, kv1_mount):
        mount, _expected = kv1_mount
        source = VaultSource(
            url=vault_url,
            token=vault_root_token,
            path="does/not/exist",
            mount_point=mount,
            kv_version=1,
        )
        with pytest.raises(KeyError, match="Vault path not found"):
            source.load_raw()


@pytest.mark.usefixtures("_reset_config")
class TestVaultSourceAppRole:
    def test_login_and_read(self, vault_url, approle_creds, kv2_secret):
        role_id, secret_id = approle_creds
        source = VaultSource(
            url=vault_url,
            role_id=role_id,
            secret_id=secret_id,
            path=KV2_PATH,
        )
        assert source.load_raw().data == kv2_secret

    @pytest.mark.usefixtures("kv2_secret")
    def test_invalid_role_id_raises(self, vault_url, approle_creds):
        _role_id, secret_id = approle_creds
        source = VaultSource(
            url=vault_url,
            role_id="ccd5c5fa-e4be-486f-ba33-125b235d8b34",
            secret_id=secret_id,
            path=KV2_PATH,
        )
        with pytest.raises(Exception):  # noqa: B017, PT011
            source.load_raw()


@pytest.mark.usefixtures("_reset_config", "kv2_secret")
class TestVaultSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="creds_from_configure"),
            pytest.param("env", id="creds_from_env"),
        ],
    )
    def test_load_with_creds(self, via, vault_url, vault_root_token, monkeypatch):
        if via == "configure":
            configure(vault={"url": vault_url, "token": vault_root_token})
        else:
            monkeypatch.setenv("DATURE_VAULT__URL", vault_url)
            monkeypatch.setenv("DATURE_VAULT__TOKEN", vault_root_token)

        @dataclass
        class Config:
            db_password: str
            port: int
            name: str

        result = load(VaultSource(path=KV2_PATH), schema=Config)
        assert result == Config(db_password="s3cret", port=5432, name="myapp")
