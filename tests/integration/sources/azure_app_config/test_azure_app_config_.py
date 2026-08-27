"""Integration tests for AzureAppConfigSource — require a live App Configuration emulator container.

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
from azure.appconfiguration import AzureAppConfigurationClient, ConfigurationSetting
from testcontainers.core.container import DockerContainer

from dature import AzureAppConfigSource, configure, load
from dature.errors import DatureConfigError
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.integration.azure_credentials import NoopCredential
from tests.integration.sources.azure_app_config.helpers import (
    APP_CONFIG_INTERNAL_PORT,
    HMAC_ACCESS_KEY_ID,
    HMAC_ACCESS_KEY_SECRET,
    app_config_endpoint,
    start_app_config_container,
)
from tests.sources.checker import assert_all_types_equal

KV_PREFIX: Final = "myapp"
EXPECTED_SECRET: Final = {"db_password": "s3cret", "port": "5432", "name": "myapp"}


@dataclass
class _Config:
    db_password: str
    port: int
    name: str


EXPECTED_DATACLASS: Final = _Config(db_password="s3cret", port=5432, name="myapp")


def _hmac_connection_string(endpoint: str, *, secret: str = HMAC_ACCESS_KEY_SECRET) -> str:
    return f"Endpoint={endpoint};Id={HMAC_ACCESS_KEY_ID};Secret={secret}"


@pytest.fixture
def azure_app_config_client(azure_app_config_endpoint: str) -> AzureAppConfigurationClient:
    return AzureAppConfigurationClient.from_connection_string(_hmac_connection_string(azure_app_config_endpoint))


@pytest.fixture
def _kv_tree(azure_app_config_client: AzureAppConfigurationClient):
    for key, value in EXPECTED_SECRET.items():
        azure_app_config_client.set_configuration_setting(ConfigurationSetting(key=f"{KV_PREFIX}:{key}", value=value))


@pytest.fixture
def _kv_all_types(azure_app_config_client: AzureAppConfigurationClient, all_types_azure_app_config_file: Path):
    kv_map = json.loads(all_types_azure_app_config_file.read_text())
    for key, value in kv_map.items():
        azure_app_config_client.set_configuration_setting(ConfigurationSetting(key=key, value=value))


def _make_source(azure_app_config_endpoint: str, **kwargs: object) -> AzureAppConfigSource:
    kwargs.setdefault("key_filter", f"{KV_PREFIX}:*")
    kwargs.setdefault("prefix", KV_PREFIX)
    return AzureAppConfigSource(connection_string=_hmac_connection_string(azure_app_config_endpoint), **kwargs)


@pytest.mark.usefixtures("_reset_config")
class TestAzureAppConfigSourceBasic:
    @pytest.mark.usefixtures("_kv_tree")
    def test_load_basic(self, azure_app_config_endpoint: str):
        result = load(_make_source(azure_app_config_endpoint), schema=_Config)

        assert result == EXPECTED_DATACLASS

    def test_missing_key_filter_raises(self, azure_app_config_endpoint: str):
        with pytest.raises(DatureConfigError) as exc_info:
            load(_make_source(azure_app_config_endpoint, key_filter="does-not-exist:*"), schema=_Config)

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)


@pytest.mark.usefixtures("_reset_config")
class TestAzureAppConfigSourceAllTypes:
    @pytest.mark.usefixtures("_kv_all_types")
    def test_comprehensive_type_conversion(self, azure_app_config_endpoint: str):
        result = load(
            _make_source(azure_app_config_endpoint, key_filter="all_types:*", prefix="all_types"),
            schema=AllPythonTypesCompact,
        )

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config", "_kv_tree")
class TestAzureAppConfigSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="connection_string_from_configure"),
            pytest.param("env", id="connection_string_from_env"),
        ],
    )
    def test_load_with_settings(self, via: str, azure_app_config_endpoint: str, monkeypatch: pytest.MonkeyPatch):
        connection_string = _hmac_connection_string(azure_app_config_endpoint)
        if via == "configure":
            configure(azure_app_config={"connection_string": connection_string})
        else:
            monkeypatch.setenv("DATURE_AZURE_APP_CONFIG__CONNECTION_STRING", connection_string)

        result = load(
            AzureAppConfigSource(key_filter=f"{KV_PREFIX}:*", prefix=KV_PREFIX),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS


@pytest.fixture(scope="class")
def azure_app_config_auth_container() -> Generator[DockerContainer]:
    """A dedicated container with anonymous auth disabled and HMAC enabled — auth mode is
    fixed at container start, so the package-scoped anonymous container every other test
    reads from can't be reused here."""
    yield from start_app_config_container(APP_CONFIG_INTERNAL_PORT, anonymous=False, hmac=True)


@pytest.fixture(scope="class")
def azure_app_config_auth_endpoint(azure_app_config_auth_container: DockerContainer) -> str:
    return app_config_endpoint(azure_app_config_auth_container, APP_CONFIG_INTERNAL_PORT)


@pytest.mark.usefixtures("_reset_config")
class TestAzureAppConfigSourceAuth:
    @pytest.fixture(autouse=True)
    def _seed_secret(self, azure_app_config_auth_endpoint: str):
        client = AzureAppConfigurationClient.from_connection_string(
            _hmac_connection_string(azure_app_config_auth_endpoint)
        )
        for key, value in EXPECTED_SECRET.items():
            client.set_configuration_setting(ConfigurationSetting(key=f"{KV_PREFIX}:{key}", value=value))

    def test_correct_hmac_connection_string_loads(self, azure_app_config_auth_endpoint: str):
        result = load(
            AzureAppConfigSource(
                connection_string=_hmac_connection_string(azure_app_config_auth_endpoint),
                key_filter=f"{KV_PREFIX}:*",
                prefix=KV_PREFIX,
            ),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS

    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("wrong_secret", id="wrong_secret"),
            pytest.param("bearer_credential", id="bearer_credential_when_only_hmac_enabled"),
        ],
    )
    def test_bad_auth_raises_permission_error(self, via: str, azure_app_config_auth_endpoint: str):
        if via == "wrong_secret":
            source = AzureAppConfigSource(
                connection_string=_hmac_connection_string(azure_app_config_auth_endpoint, secret="d3Jvbmctc2VjcmV0"),
                key_filter=f"{KV_PREFIX}:*",
                prefix=KV_PREFIX,
            )
        else:
            source = AzureAppConfigSource(
                endpoint=azure_app_config_auth_endpoint,
                credential=NoopCredential(),
                key_filter=f"{KV_PREFIX}:*",
                prefix=KV_PREFIX,
                request_options={"enforce_https": False},
            )

        with pytest.raises(DatureConfigError) as exc_info:
            load(source, schema=_Config)

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, PermissionError)
        assert inner.args[0] == (
            f"Azure App Configuration auth failed for azure-app-config://{azure_app_config_auth_endpoint} "
            f"key={KV_PREFIX}:*"
        )
