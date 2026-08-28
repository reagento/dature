"""Unit tests for azure_app_config_ module (AzureAppConfigSource).

Container-based integration tests live in ``tests/integration/sources/azure_app_config/``.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ResourceNotFoundError

from dature import AzureAppConfigSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group
from dature.loading.source_validation import validate_source
from dature.sources.base import remote_value_loaders, string_value_loaders
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestAzureAppConfigSourceDisplayProperties:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("format_name", "azure-app-config", id="format_name"),
            pytest.param("location_label", "AZURE_APP_CONFIG", id="location_label"),
            pytest.param("config_group", "azure_app_config", id="config_group"),
        ],
    )
    def test_class_attribute(self, attr, expected):
        assert getattr(AzureAppConfigSource, attr) == expected

    @pytest.mark.parametrize(
        ("decode", "expected"),
        [
            pytest.param("utf-8", string_value_loaders(), id="utf8"),
            pytest.param("json", remote_value_loaders(), id="json"),
        ],
    )
    def test_format_loaders(self, decode, expected):
        src = AzureAppConfigSource(endpoint="https://x.azconfig.io", decode=decode)

        assert src.format_loaders() == expected

    def test_format_loaders_raises_on_unknown_decode(self):
        src = AzureAppConfigSource(endpoint="https://x.azconfig.io", decode="xml")

        with pytest.raises(ValueError, match="Unknown decode mode: 'xml'"):
            src.format_loaders()

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            pytest.param(
                {"endpoint": "https://x.azconfig.io"}, "azure-app-config://https://x.azconfig.io", id="endpoint"
            ),
            pytest.param(
                {"connection_string": "Endpoint=https://x.azconfig.io;Id=abc;Secret=SHOULD_NOT_APPEAR"},
                "azure-app-config://https://x.azconfig.io",
                id="connection_string_hides_secret",
            ),
            pytest.param(
                {"endpoint": "https://x.azconfig.io", "key_filter": "myapp:*"},
                "azure-app-config://https://x.azconfig.io key=myapp:*",
                id="with_key_filter",
            ),
            pytest.param(
                {"endpoint": "https://x.azconfig.io", "label_filter": "prod"},
                "azure-app-config://https://x.azconfig.io label=prod",
                id="with_label_filter",
            ),
        ],
    )
    def test_remote_address(self, kwargs, expected):
        src = AzureAppConfigSource(**kwargs)

        assert src.remote_address() == expected

    def test_remote_address_never_contains_secret(self):
        src = AzureAppConfigSource(connection_string="Endpoint=https://x.azconfig.io;Id=abc;Secret=SHOULD_NOT_APPEAR")

        assert "SHOULD_NOT_APPEAR" not in src.remote_address()
        assert "SHOULD_NOT_APPEAR" not in repr(src)


@pytest.mark.usefixtures("_reset_config")
class TestAzureAppConfigSourceValidation:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            pytest.param({}, "exactly one of endpoint or connection_string", id="neither_set"),
            pytest.param(
                {"endpoint": "https://x.azconfig.io", "connection_string": "Endpoint=https://x.azconfig.io"},
                "exactly one of endpoint or connection_string",
                id="both_set",
            ),
            pytest.param(
                {"endpoint": "https://x.azconfig.io", "tenant_id": "t"},
                "must be set together",
                id="partial_service_principal",
            ),
            pytest.param(
                {
                    "connection_string": "Endpoint=https://x.azconfig.io",
                    "tenant_id": "t",
                    "client_id": "c",
                    "client_secret": "s",
                },
                "mutually exclusive",
                id="connection_string_with_service_principal",
            ),
        ],
    )
    def test_validate_raises_when_invalid(self, kwargs, match):
        merged = apply_source_config_group(AzureAppConfigSource(**kwargs))

        with pytest.raises(ValueError, match=match):
            validate_source(merged)

    def test_validate_passes_with_endpoint(self):
        merged = apply_source_config_group(AzureAppConfigSource(endpoint="https://x.azconfig.io"))

        validate_source(merged)

    def test_validate_passes_with_connection_string(self):
        merged = apply_source_config_group(AzureAppConfigSource(connection_string="Endpoint=https://x.azconfig.io"))

        validate_source(merged)


@pytest.mark.usefixtures("_reset_config")
class TestAzureAppConfigSourceConfigFallback:
    def test_endpoint_from_configure(self):
        configure(azure_app_config={"endpoint": "https://from-configure.azconfig.io"})

        merged = apply_source_config_group(AzureAppConfigSource())

        assert merged.endpoint == "https://from-configure.azconfig.io"

    def test_endpoint_from_env_var(self, monkeypatch):
        monkeypatch.setenv("DATURE_AZURE_APP_CONFIG__ENDPOINT", "https://from-env.azconfig.io")

        merged = apply_source_config_group(AzureAppConfigSource())

        assert merged.endpoint == "https://from-env.azconfig.io"

    def test_instance_overrides_global(self):
        configure(azure_app_config={"endpoint": "https://global.azconfig.io"})

        merged = apply_source_config_group(AzureAppConfigSource(endpoint="https://instance.azconfig.io"))

        assert merged.endpoint == "https://instance.azconfig.io"


class FakeSetting:
    def __init__(self, key: str, value: str, content_type: str | None = None) -> None:
        self.key = key
        self.value = value
        self.content_type = content_type


class FakeAppConfigClient:
    def __init__(self, *, settings: "list[FakeSetting] | None" = None, error: Exception | None = None) -> None:
        self._settings = settings if settings is not None else []
        self._error = error
        self.list_kwargs: dict[str, object] | None = None
        self.init_kwargs: dict[str, object] = {}
        self.from_connection_string_args: tuple[str, dict[str, object]] | None = None

    def list_configuration_settings(self, **kwargs: object) -> "list[FakeSetting]":
        self.list_kwargs = kwargs
        if self._error is not None:
            raise self._error
        return list(self._settings)


def _fake_client_factory(client: FakeAppConfigClient) -> object:
    class _Factory:
        def __call__(self, *args: object, **kwargs: object) -> FakeAppConfigClient:  # noqa: ARG002
            client.init_kwargs = kwargs
            return client

        @staticmethod
        def from_connection_string(connection_string: str, **kwargs: object) -> FakeAppConfigClient:
            client.from_connection_string_args = (connection_string, kwargs)
            return client

    return _Factory()


@dataclass
class _FetchConfig:
    foo: str = field(default="")


class TestAzureAppConfigSourceFetch:
    def _make_source(
        self, monkeypatch: pytest.MonkeyPatch, client: FakeAppConfigClient, **kwargs: object
    ) -> AzureAppConfigSource:
        monkeypatch.setattr("azure.appconfiguration.AzureAppConfigurationClient", _fake_client_factory(client))
        kwargs.setdefault("endpoint", "https://x.azconfig.io")
        kwargs.setdefault("credential", object())
        kwargs.setdefault("expand_env_vars", "default")
        return AzureAppConfigSource(**kwargs)

    def test_nests_on_separator(self, monkeypatch):
        client = FakeAppConfigClient(
            settings=[
                FakeSetting("myapp:db:host", "localhost"),
                FakeSetting("myapp:db:port", "5432"),
                FakeSetting("myapp:name", "svc"),
            ]
        )
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {
            "myapp": {"db": {"host": "localhost", "port": "5432"}, "name": "svc"},
        }

    def test_separator_none_keeps_flat_keys(self, monkeypatch):
        client = FakeAppConfigClient(settings=[FakeSetting("myapp:db:host", "localhost")])
        src = self._make_source(monkeypatch, client, separator=None)

        result = src.load_raw()

        assert result.loaded_data == {"myapp:db:host": "localhost"}

    def test_content_type_json_always_parsed(self, monkeypatch):
        client = FakeAppConfigClient(
            settings=[FakeSetting("db", '{"host": "localhost"}', content_type="application/json")]
        )
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"db": {"host": "localhost"}}

    def test_uses_connection_string_when_set(self, monkeypatch):
        client = FakeAppConfigClient(settings=[FakeSetting("a", "1")])
        src = self._make_source(
            monkeypatch, client, endpoint=None, connection_string="Endpoint=https://x.azconfig.io;Id=i;Secret=s"
        )

        src.load_raw()

        assert client.from_connection_string_args is not None
        assert client.from_connection_string_args[0] == "Endpoint=https://x.azconfig.io;Id=i;Secret=s"

    def test_key_filter_and_label_filter_passed_through(self, monkeypatch):
        client = FakeAppConfigClient(settings=[FakeSetting("a", "1")])
        src = self._make_source(monkeypatch, client, key_filter="myapp:*", label_filter="prod")

        src.load_raw()

        assert client.list_kwargs == {"key_filter": "myapp:*", "label_filter": "prod"}

    def test_client_options_forwarded(self, monkeypatch):
        client = FakeAppConfigClient(settings=[FakeSetting("a", "1")])
        src = self._make_source(monkeypatch, client, client_options={"api_version": "2023-11-01"})

        src.load_raw()

        assert client.init_kwargs["api_version"] == "2023-11-01"

    def test_request_options_forwarded(self, monkeypatch):
        client = FakeAppConfigClient(settings=[FakeSetting("a", "1")])
        src = self._make_source(monkeypatch, client, request_options={"enforce_https": False})

        src.load_raw()

        assert client.list_kwargs["enforce_https"] is False

    def test_empty_result_raises_key_error(self, monkeypatch):
        client = FakeAppConfigClient(settings=[])
        src = self._make_source(monkeypatch, client)

        with pytest.raises(KeyError, match="Azure App Configuration key\\(s\\) not found"):
            src.load_raw()

    def test_resource_not_found_raises_key_error(self, monkeypatch):
        client = FakeAppConfigClient(error=ResourceNotFoundError("nope"))
        src = self._make_source(monkeypatch, client)

        with pytest.raises(KeyError, match="Azure App Configuration key\\(s\\) not found"):
            src.load_raw()

    def test_client_authentication_error_raises_permission_error(self, monkeypatch):
        client = FakeAppConfigClient(error=ClientAuthenticationError("nope"))
        src = self._make_source(monkeypatch, client)

        with pytest.raises(PermissionError, match="Azure App Configuration auth failed"):
            src.load_raw()

    @pytest.mark.parametrize("status_code", [401, 403])
    def test_http_error_401_403_raises_permission_error(self, monkeypatch, status_code):
        error = HttpResponseError("nope")
        error.status_code = status_code
        client = FakeAppConfigClient(error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(PermissionError, match="Azure App Configuration auth failed"):
            src.load_raw()

    def test_other_http_error_propagates(self, monkeypatch):
        error = HttpResponseError("boom")
        error.status_code = 500
        client = FakeAppConfigClient(error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(HttpResponseError):
            src.load_raw()

    def test_comprehensive_type_conversion(self, monkeypatch, all_types_azure_app_config_file: Path):
        """Test loading via AzureAppConfigSource (decode='utf-8') with full type coercion."""
        kv_map = json.loads(all_types_azure_app_config_file.read_text())
        settings = [FakeSetting(key, value) for key, value in kv_map.items()]
        client = FakeAppConfigClient(settings=settings)
        src = self._make_source(monkeypatch, client, prefix="all_types")

        result = load(src, schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_missing_key_error_message_includes_address(self, monkeypatch):
        client = FakeAppConfigClient(settings=[])
        self._make_source(monkeypatch, client)

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                AzureAppConfigSource(endpoint="https://x.azconfig.io", credential=object()),
                schema=_FetchConfig,
            )

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "'Azure App Configuration key(s) not found: azure-app-config://https://x.azconfig.io'"
        )


@pytest.mark.usefixtures("_reset_config")
def test_missing_azure_appconfiguration_raises_on_load(monkeypatch):
    """`import dature` works without azure-appconfiguration; only _fetch() requires it.

    ``sys.modules[name] = None`` is the reliable way to simulate a missing dependency for a
    dotted package name — unlike ``block_import`` (which patches ``importlib.import_module``
    only), it blocks *any* import mechanism, since Python's import system raises
    ``ImportError`` immediately whenever a ``sys.modules`` entry is ``None``.
    """
    monkeypatch.setenv("DATURE_AZURE_APP_CONFIG__ENDPOINT", "https://x.azconfig.io")
    monkeypatch.setitem(sys.modules, "azure.appconfiguration", None)

    @dataclass
    class Config:
        foo: str = ""

    with pytest.raises(DatureConfigError) as exc_info:
        load(AzureAppConfigSource(), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == (
        "'azure.appconfiguration' is not installed. Run: pip install 'dature[azure-appconfig]'"
    )
