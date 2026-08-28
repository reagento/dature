"""Unit tests for azure_key_vault_ module (AzureKeyVaultSource).

Container-based integration tests live in ``tests/integration/sources/azure_key_vault/``.
"""

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ResourceNotFoundError

from dature import AzureKeyVaultSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group
from dature.loading.source_validation import validate_source
from dature.sources.base import remote_value_loaders, string_value_loaders
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestAzureKeyVaultSourceDisplayProperties:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("format_name", "azure-key-vault", id="format_name"),
            pytest.param("location_label", "AZURE_KEY_VAULT", id="location_label"),
            pytest.param("config_group", "azure_key_vault", id="config_group"),
        ],
    )
    def test_class_attribute(self, attr, expected):
        assert getattr(AzureKeyVaultSource, attr) == expected

    @pytest.mark.parametrize(
        ("decode", "expected"),
        [
            pytest.param("utf-8", string_value_loaders(), id="utf8"),
            pytest.param("json", remote_value_loaders(), id="json"),
        ],
    )
    def test_format_loaders(self, decode, expected):
        src = AzureKeyVaultSource(vault_url="https://x.vault.azure.net", decode=decode)

        assert src.format_loaders() == expected

    def test_format_loaders_raises_on_unknown_decode(self):
        src = AzureKeyVaultSource(vault_url="https://x.vault.azure.net", decode="xml")

        with pytest.raises(ValueError, match="Unknown decode mode: 'xml'"):
            src.format_loaders()

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            pytest.param(
                {"vault_url": "https://x.vault.azure.net"},
                "azure-key-vault://https://x.vault.azure.net/*",
                id="list_mode",
            ),
            pytest.param(
                {"vault_url": "https://x.vault.azure.net", "name": "app-config"},
                "azure-key-vault://https://x.vault.azure.net/app-config",
                id="single_secret_mode",
            ),
        ],
    )
    def test_remote_address(self, kwargs, expected):
        src = AzureKeyVaultSource(**kwargs)

        assert src.remote_address() == expected


@pytest.mark.usefixtures("_reset_config")
class TestAzureKeyVaultSourceValidation:
    def test_validate_raises_on_partial_service_principal(self):
        merged = apply_source_config_group(AzureKeyVaultSource(vault_url="https://x.vault.azure.net", tenant_id="t"))

        with pytest.raises(ValueError, match="must be set together"):
            validate_source(merged)

    def test_validate_raises_when_vault_url_missing(self):
        merged = apply_source_config_group(AzureKeyVaultSource())

        with pytest.raises(ValueError, match="vault_url is required"):
            validate_source(merged)

    def test_validate_passes_with_vault_url(self):
        merged = apply_source_config_group(AzureKeyVaultSource(vault_url="https://x.vault.azure.net"))

        validate_source(merged)


@pytest.mark.usefixtures("_reset_config")
class TestAzureKeyVaultSourceConfigFallback:
    def test_vault_url_from_configure(self):
        configure(azure_key_vault={"vault_url": "https://from-configure.vault.azure.net"})

        merged = apply_source_config_group(AzureKeyVaultSource())

        assert merged.vault_url == "https://from-configure.vault.azure.net"

    def test_vault_url_from_env_var(self, monkeypatch):
        monkeypatch.setenv("DATURE_AZURE_KEY_VAULT__VAULT_URL", "https://from-env.vault.azure.net")

        merged = apply_source_config_group(AzureKeyVaultSource())

        assert merged.vault_url == "https://from-env.vault.azure.net"

    def test_instance_overrides_global(self):
        configure(azure_key_vault={"vault_url": "https://global.vault.azure.net"})

        merged = apply_source_config_group(AzureKeyVaultSource(vault_url="https://instance.vault.azure.net"))

        assert merged.vault_url == "https://instance.vault.azure.net"


class FakeSecretProps:
    def __init__(self, name: str, *, enabled: bool | None = True) -> None:
        self.name = name
        self.enabled = enabled


class FakeKVSecret:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeSecretClient:
    def __init__(
        self,
        *,
        props: "list[FakeSecretProps] | None" = None,
        values: "dict[str, str] | None" = None,
        list_error: Exception | None = None,
        get_error: Exception | None = None,
    ) -> None:
        self._props = props if props is not None else []
        self._values = values if values is not None else {}
        self._list_error = list_error
        self._get_error = get_error
        self.init_kwargs: dict[str, object] = {}
        self.get_secret_calls: list[tuple[str, str | None]] = []

    def list_properties_of_secrets(self) -> "list[FakeSecretProps]":
        if self._list_error is not None:
            raise self._list_error
        return list(self._props)

    def get_secret(self, name: str, version: str | None = None) -> FakeKVSecret:
        self.get_secret_calls.append((name, version))
        if self._get_error is not None:
            raise self._get_error
        return FakeKVSecret(self._values[name])


def _fake_client_factory(client: FakeSecretClient) -> "Callable[..., FakeSecretClient]":
    def _factory(*args: object, **kwargs: object) -> FakeSecretClient:  # noqa: ARG001
        client.init_kwargs = kwargs
        return client

    return _factory


@dataclass
class _FetchConfig:
    foo: str = ""


class TestAzureKeyVaultSourceFetch:
    def _make_source(
        self, monkeypatch: pytest.MonkeyPatch, client: FakeSecretClient, **kwargs: object
    ) -> AzureKeyVaultSource:
        monkeypatch.setattr("azure.keyvault.secrets.SecretClient", _fake_client_factory(client))
        kwargs.setdefault("vault_url", "https://x.vault.azure.net")
        kwargs.setdefault("credential", object())
        kwargs.setdefault("expand_env_vars", "default")
        return AzureKeyVaultSource(**kwargs)

    def test_single_secret_mode(self, monkeypatch):
        client = FakeSecretClient(values={"app-config": '{"host": "localhost"}'})
        src = self._make_source(monkeypatch, client, name="app-config", decode="json")

        result = src.load_raw()

        assert result.loaded_data == {"host": "localhost"}

    def test_single_secret_mode_passes_version(self, monkeypatch):
        client = FakeSecretClient(values={"app-config": "v"})
        src = self._make_source(monkeypatch, client, name="app-config", version="abc123")

        src.load_raw()

        assert client.get_secret_calls == [("app-config", "abc123")]

    def test_list_mode_nests_on_separator(self, monkeypatch):
        client = FakeSecretClient(
            props=[FakeSecretProps("db--host"), FakeSecretProps("db--port"), FakeSecretProps("name")],
            values={"db--host": "localhost", "db--port": "5432", "name": "svc"},
        )
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"db": {"host": "localhost", "port": "5432"}, "name": "svc"}

    def test_list_mode_skips_disabled_secrets(self, monkeypatch):
        client = FakeSecretClient(
            props=[FakeSecretProps("a"), FakeSecretProps("b", enabled=False)],
            values={"a": "1"},
        )
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"a": "1"}

    def test_list_mode_keeps_secret_with_unknown_enabled_state(self, monkeypatch):
        client = FakeSecretClient(
            props=[FakeSecretProps("a", enabled=None)],
            values={"a": "1"},
        )
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"a": "1"}

    def test_client_options_forwarded(self, monkeypatch):
        client = FakeSecretClient(values={"app-config": "v"})
        src = self._make_source(monkeypatch, client, name="app-config", client_options={"api_version": "7.6"})

        src.load_raw()

        assert client.init_kwargs["api_version"] == "7.6"

    def test_empty_vault_raises_key_error(self, monkeypatch):
        client = FakeSecretClient(props=[])
        src = self._make_source(monkeypatch, client)

        with pytest.raises(KeyError, match="Azure Key Vault has no secrets"):
            src.load_raw()

    def test_resource_not_found_raises_key_error(self, monkeypatch):
        client = FakeSecretClient(get_error=ResourceNotFoundError("nope"))
        src = self._make_source(monkeypatch, client, name="missing")

        with pytest.raises(KeyError, match="Azure Key Vault secret not found"):
            src.load_raw()

    def test_client_authentication_error_raises_permission_error(self, monkeypatch):
        client = FakeSecretClient(list_error=ClientAuthenticationError("nope"))
        src = self._make_source(monkeypatch, client)

        with pytest.raises(PermissionError, match="Azure Key Vault auth failed"):
            src.load_raw()

    @pytest.mark.parametrize("status_code", [401, 403])
    def test_http_error_401_403_raises_permission_error(self, monkeypatch, status_code):
        error = HttpResponseError("nope")
        error.status_code = status_code
        client = FakeSecretClient(list_error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(PermissionError, match="Azure Key Vault auth failed"):
            src.load_raw()

    def test_other_http_error_propagates(self, monkeypatch):
        error = HttpResponseError("boom")
        error.status_code = 500
        client = FakeSecretClient(list_error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(HttpResponseError):
            src.load_raw()

    def test_comprehensive_type_conversion(self, monkeypatch, all_types_azure_key_vault_file: Path):
        """Test loading via AzureKeyVaultSource (decode='utf-8') with full type coercion."""
        kv_map = json.loads(all_types_azure_key_vault_file.read_text())
        props = [FakeSecretProps(key) for key in kv_map]
        client = FakeSecretClient(props=props, values=kv_map)
        src = self._make_source(monkeypatch, client)

        result = load(src, schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_missing_secret_error_message_includes_address(self, monkeypatch):
        client = FakeSecretClient(props=[])
        self._make_source(monkeypatch, client)

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                AzureKeyVaultSource(vault_url="https://x.vault.azure.net", credential=object()),
                schema=_FetchConfig,
            )

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "'Azure Key Vault has no secrets: azure-key-vault://https://x.vault.azure.net/*'"
        )


@pytest.mark.usefixtures("_reset_config")
def test_missing_azure_keyvault_secrets_raises_on_load(monkeypatch):
    """`import dature` works without azure-keyvault-secrets; only _fetch() requires it.

    ``sys.modules[name] = None`` is the reliable way to simulate a missing dependency for a
    dotted package name — unlike ``block_import`` (which patches ``importlib.import_module``
    only), it blocks *any* import mechanism, since Python's import system raises
    ``ImportError`` immediately whenever a ``sys.modules`` entry is ``None``.
    """
    monkeypatch.setenv("DATURE_AZURE_KEY_VAULT__VAULT_URL", "https://x.vault.azure.net")
    monkeypatch.setitem(sys.modules, "azure.keyvault.secrets", None)

    @dataclass
    class Config:
        foo: str = ""

    with pytest.raises(DatureConfigError) as exc_info:
        load(AzureKeyVaultSource(), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == (
        "'azure.keyvault.secrets' is not installed. Run: pip install 'dature[azure-keyvault]'"
    )
