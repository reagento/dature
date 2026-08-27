import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Literal, cast

from adaptix.provider import Provider

from dature._deps import require_dep
from dature.sources.base import RemoteSource, string_value_loaders
from dature.type_aliases import JSONValue
from dature.validators.root import RootPredicate
from dature.validators.v import V


@dataclass(kw_only=True, repr=False)
class AzureKeyVaultSource(RemoteSource):
    vault_url: Annotated[
        str,
        (V.len() >= 1).with_error_message(
            "vault_url is required (set on instance or via configure(azure_key_vault={...}) / "
            "DATURE_AZURE_KEY_VAULT__VAULT_URL)"
        ),
    ] = ""

    name: str = "*"
    """A single secret name holding the whole config document. ``"*"`` (default) lists every
    secret in the vault and nests them by ``separator`` instead (N+1 round-trip: one list + one
    ``get_secret`` per name). Safe sentinel: secret names only allow ``[0-9A-Za-z-]``, so ``*``
    can never be a real secret name."""

    version: str | None = None

    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None

    credential: object | None = None
    """Pre-built ``azure.core.credentials.TokenCredential``. Takes precedence over
    tenant_id/client_id/client_secret and the ``DefaultAzureCredential`` fallback."""

    client_options: Mapping[str, Any] | None = None
    """Extra kwargs forwarded to ``SecretClient`` (``api_version``, ``transport``,
    ``verify_challenge_resource``, ...) — required to target test doubles like lowkey-vault."""

    separator: str | None = "--"
    """Secret names only allow ``[0-9A-Za-z-]``, so ``-`` cannot double as both a nesting
    separator and a literal character; the two-dash default keeps the two distinguishable."""
    decode: Literal["utf-8", "json"] = "utf-8"

    format_name: str = "azure-key-vault"
    location_label: str = "AZURE_KEY_VAULT"
    config_group: str | None = "azure_key_vault"

    root_validators: ClassVar[tuple[RootPredicate, ...]] = (
        V.root(
            lambda s: len({s.tenant_id is None, s.client_id is None, s.client_secret is None}) == 1,
            error_message="tenant_id, client_id and client_secret must be set together",
        ),
    )

    def remote_address(self) -> str:
        return f"azure-key-vault://{self.vault_url}/{self.name}"

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

    def _decode_raw(self, raw: str | None) -> JSONValue:
        raw = raw or ""
        match self.decode:
            case "json":
                return cast("JSONValue", json.loads(raw))
            case "utf-8":
                return raw
            case _ as unknown:
                msg = f"Unknown decode mode: {unknown!r}"
                raise ValueError(msg)

    def _fetch(self) -> JSONValue:
        require_dep("azure.keyvault.secrets", "azure-keyvault")
        from azure.core.credentials import TokenCredential  # noqa: PLC0415
        from azure.core.exceptions import (  # noqa: PLC0415
            ClientAuthenticationError,
            HttpResponseError,
            ResourceNotFoundError,
        )
        from azure.keyvault.secrets import SecretClient  # noqa: PLC0415

        options = dict(self.client_options) if self.client_options else {}
        client = SecretClient(
            vault_url=self.vault_url,
            credential=cast("TokenCredential", self._build_credential()),
            **options,
        )

        try:
            if self.name != "*":
                secret = client.get_secret(self.name, self.version)
                return self._decode_raw(secret.value)

            names = [
                props.name
                for props in client.list_properties_of_secrets()
                if props.enabled is not False and props.name is not None
            ]
            if not names:
                msg = f"Azure Key Vault has no secrets: {self.remote_address()}"
                raise KeyError(msg) from None

            secrets = [(secret_name, client.get_secret(secret_name).value) for secret_name in names]
        except ResourceNotFoundError:
            msg = f"Azure Key Vault secret not found: {self.remote_address()}"
            raise KeyError(msg) from None
        except ClientAuthenticationError:
            msg = f"Azure Key Vault auth failed for {self.remote_address()}"
            raise PermissionError(msg) from None
        except HttpResponseError as exc:
            if exc.status_code in (401, 403):
                msg = f"Azure Key Vault auth failed for {self.remote_address()}"
                raise PermissionError(msg) from None
            raise

        return self._nest_flat_keys(
            secrets,
            key_fn=lambda item: item[0],
            value_fn=lambda item: self._decode_raw(item[1]),
            separator=self.separator,
        )

    def _decodes_to_strings(self) -> bool:
        return self.decode == "utf-8"
