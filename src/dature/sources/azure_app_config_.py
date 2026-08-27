import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, cast

from adaptix.provider import Provider

from dature._deps import require_dep
from dature.sources.base import RemoteSource, string_value_loaders
from dature.type_aliases import JSONValue
from dature.validators.root import RootPredicate
from dature.validators.v import V


@dataclass(kw_only=True, repr=False)
class AzureAppConfigSource(RemoteSource):
    endpoint: str | None = None
    """App Configuration store endpoint, e.g. ``https://my-store.azconfig.io``."""

    connection_string: str | None = None
    """Mutually exclusive with ``endpoint``/``credential`` — carries its own auth."""

    key_filter: str | None = None
    """Glob passed to the SDK, e.g. ``myapp:*``. ``None`` fetches every key."""

    label_filter: str | None = None

    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None

    credential: object | None = None
    """Pre-built ``azure.core.credentials.TokenCredential``. Takes precedence over
    tenant_id/client_id/client_secret and the ``DefaultAzureCredential`` fallback."""

    client_options: Mapping[str, Any] | None = None
    """Extra kwargs forwarded to the SDK client constructor (``api_version``, ``transport``,
    a custom ``connection_verify``, ...)."""

    request_options: dict[str, Any] = field(default_factory=dict)
    """Extra kwargs forwarded to the SDK ``list_configuration_settings`` call (``fields``,
    ``tags_filter``, ``accept_datetime``, ``enforce_https``, ...). Distinct from
    ``client_options``, which reaches the client constructor."""

    separator: str | None = ":"
    decode: Literal["utf-8", "json"] = "utf-8"

    format_name: str = "azure-app-config"
    location_label: str = "AZURE_APP_CONFIG"
    config_group: str | None = "azure_app_config"

    connection_string_placeholder: str = "<connection_string>"
    """Fallback host label for ``remote_address()`` when ``connection_string`` has no
    ``Endpoint=`` part to extract."""

    root_validators: ClassVar[tuple[RootPredicate, ...]] = (
        V.root(
            lambda s: (s.endpoint is None) != (s.connection_string is None),
            error_message="exactly one of endpoint or connection_string must be set "
            "(set endpoint on instance or via configure(azure_app_config={...}) / "
            "DATURE_AZURE_APP_CONFIG__ENDPOINT)",
        ),
        V.root(
            lambda s: len({s.tenant_id is None, s.client_id is None, s.client_secret is None}) == 1,
            error_message="tenant_id, client_id and client_secret must be set together",
        ),
        V.root(
            lambda s: s.connection_string is None or (s.credential is None and s.tenant_id is None),
            error_message="connection_string is mutually exclusive with credential and "
            "tenant_id/client_id/client_secret",
        ),
    )

    def remote_address(self) -> str:
        host = self.endpoint or _extract_endpoint(self.connection_string) or self.connection_string_placeholder
        suffix = ""
        if self.key_filter is not None:
            suffix += f" key={self.key_filter}"
        if self.label_filter is not None:
            suffix += f" label={self.label_filter}"
        return f"azure-app-config://{host}{suffix}"

    def format_loaders(self) -> "list[Provider]":
        match self.decode:
            case "utf-8":
                return string_value_loaders()
            case "json":
                return super().format_loaders()
            case _ as unknown:
                msg = f"Unknown decode mode: {unknown!r}"
                raise ValueError(msg)

    def _build_credential(self) -> object:
        from azure.identity import ClientSecretCredential, DefaultAzureCredential  # noqa: PLC0415

        if self.credential is not None:
            return self.credential
        if self.tenant_id is not None:
            return ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=cast("str", self.client_id),
                client_secret=cast("str", self.client_secret),
            )
        return DefaultAzureCredential()

    def _decode_setting(self, setting: Any) -> JSONValue:  # noqa: ANN401
        if setting.content_type == "application/json":
            return cast("JSONValue", json.loads(setting.value))
        match self.decode:
            case "json":
                return cast("JSONValue", json.loads(setting.value))
            case "utf-8":
                return cast("str", setting.value)
            case _ as unknown:
                msg = f"Unknown decode mode: {unknown!r}"
                raise ValueError(msg)

    def _fetch(self) -> JSONValue:
        require_dep("azure.appconfiguration", "azure-appconfig")
        from azure.appconfiguration import AzureAppConfigurationClient  # noqa: PLC0415
        from azure.core.credentials import TokenCredential  # noqa: PLC0415
        from azure.core.exceptions import (  # noqa: PLC0415
            ClientAuthenticationError,
            HttpResponseError,
            ResourceNotFoundError,
        )

        options = dict(self.client_options) if self.client_options else {}
        if self.connection_string is not None:
            client = AzureAppConfigurationClient.from_connection_string(self.connection_string, **options)
        else:
            client = AzureAppConfigurationClient(
                base_url=cast("str", self.endpoint),
                credential=cast("TokenCredential", self._build_credential()),
                **options,
            )

        try:
            settings = list(
                client.list_configuration_settings(
                    key_filter=self.key_filter, label_filter=self.label_filter, **self.request_options
                )
            )
        except ResourceNotFoundError:
            msg = f"Azure App Configuration key(s) not found: {self.remote_address()}"
            raise KeyError(msg) from None
        except ClientAuthenticationError:
            msg = f"Azure App Configuration auth failed for {self.remote_address()}"
            raise PermissionError(msg) from None
        except HttpResponseError as exc:
            if exc.status_code in (401, 403):
                msg = f"Azure App Configuration auth failed for {self.remote_address()}"
                raise PermissionError(msg) from None
            raise

        if not settings:
            msg = f"Azure App Configuration key(s) not found: {self.remote_address()}"
            raise KeyError(msg) from None

        return self._nest_flat_keys(
            settings,
            key_fn=lambda s: s.key,
            value_fn=self._decode_setting,
            separator=self.separator,
        )

    def _decodes_to_strings(self) -> bool:
        return self.decode == "utf-8"


def _extract_endpoint(connection_string: str | None) -> str | None:
    if connection_string is None:
        return None
    for part in connection_string.split(";"):
        if part.startswith("Endpoint="):
            return part.removeprefix("Endpoint=")
    return None
