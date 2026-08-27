"""Integration tests for AzureKeyVaultSource — require a live lowkey-vault container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.

Unlike the Azure App Configuration emulator (which verifies HMAC signatures and lets
``TestAzureAppConfigSourceAuth`` force a genuine auth failure with a wrong secret), lowkey-vault
does not validate credential values — it only checks that a credential is present, short of the
last-resort ``LOWKEY_ENABLE_AUTH=false`` flag that disables auth checking altogether. So there is
no integration-level auth-failure case to add here; ``PermissionError`` mapping for
``ClientAuthenticationError``/``HttpResponseError`` is covered by the unit tests in
``tests/sources/test_azure_key_vault_.py``.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest
from azure.keyvault.secrets import SecretClient

from dature import AzureKeyVaultSource, configure, load
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.integration.azure_credentials import NoopCredential
from tests.sources.checker import assert_all_types_equal

EXPECTED_SECRET: Final = {"password": "s3cret", "port": "5432", "name": "myapp"}


@dataclass
class _Config:
    password: str
    port: int
    name: str


EXPECTED_DATACLASS: Final = _Config(password="s3cret", port=5432, name="myapp")


ClientOptions = dict[str, object]


@pytest.fixture
def azure_key_vault_client(azure_key_vault_url: str, azure_key_vault_client_options: ClientOptions) -> SecretClient:
    return SecretClient(vault_url=azure_key_vault_url, credential=NoopCredential(), **azure_key_vault_client_options)


@pytest.fixture
def _secrets(azure_key_vault_client: SecretClient):
    for name, value in EXPECTED_SECRET.items():
        azure_key_vault_client.set_secret(name, value)


@pytest.fixture
def _secrets_all_types(azure_key_vault_client: SecretClient, all_types_azure_key_vault_file: Path):
    kv_map = json.loads(all_types_azure_key_vault_file.read_text())
    for key, value in kv_map.items():
        azure_key_vault_client.set_secret(key, value)


def _make_source(
    azure_key_vault_url: str, azure_key_vault_client_options: ClientOptions, **kwargs: object
) -> AzureKeyVaultSource:
    return AzureKeyVaultSource(
        vault_url=azure_key_vault_url,
        credential=NoopCredential(),
        client_options=azure_key_vault_client_options,
        **kwargs,
    )


@pytest.mark.usefixtures("_reset_config")
class TestAzureKeyVaultSourceListMode:
    @pytest.mark.usefixtures("_secrets")
    def test_load_basic(self, azure_key_vault_url: str, azure_key_vault_client_options: ClientOptions):
        result = load(_make_source(azure_key_vault_url, azure_key_vault_client_options), schema=_Config)

        assert result == EXPECTED_DATACLASS


@pytest.mark.usefixtures("_reset_config")
class TestAzureKeyVaultSourceSingleSecretMode:
    def test_load_json_document(
        self,
        azure_key_vault_client: SecretClient,
        azure_key_vault_url: str,
        azure_key_vault_client_options: ClientOptions,
    ):
        azure_key_vault_client.set_secret("app-config", json.dumps(EXPECTED_SECRET))

        result = load(
            _make_source(azure_key_vault_url, azure_key_vault_client_options, name="app-config", decode="json"),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS


@pytest.mark.usefixtures("_reset_config")
class TestAzureKeyVaultSourceAllTypes:
    @pytest.mark.usefixtures("_secrets_all_types")
    def test_comprehensive_type_conversion(
        self,
        azure_key_vault_url: str,
        azure_key_vault_client_options: ClientOptions,
    ):
        result = load(
            _make_source(azure_key_vault_url, azure_key_vault_client_options),
            schema=AllPythonTypesCompact,
        )

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config", "_secrets")
class TestAzureKeyVaultSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="vault_url_from_configure"),
            pytest.param("env", id="vault_url_from_env"),
        ],
    )
    def test_load_with_settings(
        self,
        via: str,
        azure_key_vault_url: str,
        azure_key_vault_client_options: ClientOptions,
        monkeypatch: pytest.MonkeyPatch,
    ):
        if via == "configure":
            configure(azure_key_vault={"vault_url": azure_key_vault_url})
        else:
            monkeypatch.setenv("DATURE_AZURE_KEY_VAULT__VAULT_URL", azure_key_vault_url)

        result = load(
            AzureKeyVaultSource(credential=NoopCredential(), client_options=azure_key_vault_client_options),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS
