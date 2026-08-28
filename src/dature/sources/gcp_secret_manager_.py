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
class GcpSecretManagerSource(RemoteSource):
    project_id: Annotated[
        str,
        (V.len() >= 1).with_error_message(
            "project_id is required (set on instance or via "
            "configure(gcp_secret_manager={...}) / DATURE_GCP_SECRET_MANAGER__PROJECT_ID)"
        ),
    ] = ""

    name: str = "*"
    """A single secret id holding the whole config document. ``"*"`` (default) lists every
    secret in the project and nests them by ``separator`` instead (N+1 round-trip: one list +
    one ``access_secret_version`` per id). Safe sentinel: secret ids only allow
    ``[0-9A-Za-z_-]``, so ``*`` can never be a real secret id."""

    version: str = "latest"

    name_prefix: str | None = None
    """List-mode-only: server-side ``name:<prefix>`` filter. Only valid when ``name == "*"``."""
    labels: Mapping[str, str] | None = None
    """List-mode-only: server-side ``labels.<key>=<value>`` filters, ANDed together.
    Only valid when ``name == "*"``."""

    credentials: object | None = None
    """Pre-built ``google.auth.credentials.Credentials``. Takes precedence over
    credentials_file and the Application Default Credentials fallback."""
    credentials_file: str | None = None
    """Path to a service account JSON key file."""

    transport: object | None = None
    """Pre-built ``SecretManagerServiceTransport`` (or a factory), forwarded to
    ``SecretManagerServiceClient``. Required to target test doubles that speak plaintext gRPC,
    e.g. ``SecretManagerServiceGrpcTransport(channel=grpc.insecure_channel(...))``. Mutually
    exclusive with credentials/credentials_file: the client rejects credentials alongside a
    pre-built transport."""
    client_options: Mapping[str, Any] | None = None
    """Extra kwargs forwarded to ``SecretManagerServiceClient`` (e.g. ``api_endpoint``)."""

    separator: str | None = "--"
    """Secret ids only allow ``[0-9A-Za-z_-]``, so ``-`` cannot double as both a nesting
    separator and a literal character; the two-dash default keeps the two distinguishable."""
    decode: Literal["utf-8", "json"] = "utf-8"

    format_name: str = "gcp-secret-manager"
    location_label: str = "GCP_SECRET_MANAGER"
    config_group: str | None = "gcp_secret_manager"

    root_validators: ClassVar[tuple[RootPredicate, ...]] = (
        V.root(
            lambda s: s.credentials is None or s.credentials_file is None,
            error_message="credentials and credentials_file are mutually exclusive",
        ),
        V.root(
            lambda s: s.transport is None or (s.credentials is None and s.credentials_file is None),
            error_message="transport cannot be combined with credentials or credentials_file",
        ),
        V.root(
            lambda s: s.name == "*" or (s.name_prefix is None and s.labels is None),
            error_message="name_prefix and labels only apply in list mode (name='*')",
        ),
    )

    def remote_address(self) -> str:
        return f"gcp-secret-manager://{self.project_id}/{self.name}/versions/{self.version}"

    def format_loaders(self) -> "list[Provider]":
        match self.decode:
            case "utf-8":
                return string_value_loaders()
            case "json":
                return super().format_loaders()
            case _ as unknown:
                msg = f"Unknown decode mode: {unknown!r}"
                raise ValueError(msg)

    def _build_credentials(self) -> object:
        if self.credentials is not None:
            return self.credentials
        if self.credentials_file is not None:
            from google.oauth2 import service_account  # noqa: PLC0415

            return service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                self.credentials_file
            )
        return None

    def _build_filter(self) -> str:
        parts = []
        if self.name_prefix is not None:
            parts.append(f"name:{self.name_prefix}")
        if self.labels:
            parts.extend(f"labels.{key}={value}" for key, value in sorted(self.labels.items()))
        return " AND ".join(parts)

    def _decode_raw(self, raw: str) -> JSONValue:
        match self.decode:
            case "json":
                return cast("JSONValue", json.loads(raw))
            case "utf-8":
                return raw
            case _ as unknown:
                msg = f"Unknown decode mode: {unknown!r}"
                raise ValueError(msg)

    def _fetch(self) -> JSONValue:
        require_dep("google.cloud.secretmanager", "gcp")
        from google.api_core.exceptions import NotFound, PermissionDenied, Unauthenticated  # noqa: PLC0415
        from google.auth.exceptions import DefaultCredentialsError  # noqa: PLC0415
        from google.cloud import secretmanager  # noqa: PLC0415

        options = dict(self.client_options) if self.client_options else {}
        client = secretmanager.SecretManagerServiceClient(
            credentials=cast("Any", self._build_credentials()),
            transport=cast("Any", self.transport),
            **options,
        )

        try:
            if self.name != "*":
                version_name = f"projects/{self.project_id}/secrets/{self.name}/versions/{self.version}"
                response = client.access_secret_version(name=version_name)
                return self._decode_raw(response.payload.data.decode("utf-8"))

            parent = f"projects/{self.project_id}"
            secrets = [
                secret.name.rsplit("/", 1)[-1]
                for secret in client.list_secrets(request={"parent": parent, "filter": self._build_filter()})
            ]
            if not secrets:
                msg = f"GCP Secret Manager has no secrets: {self.remote_address()}"
                raise KeyError(msg) from None

            items = [
                (
                    secret_name,
                    client.access_secret_version(
                        name=f"projects/{self.project_id}/secrets/{secret_name}/versions/{self.version}"
                    ).payload.data.decode("utf-8"),
                )
                for secret_name in secrets
            ]
        except NotFound:
            msg = f"GCP Secret Manager secret not found: {self.remote_address()}"
            raise KeyError(msg) from None
        except (PermissionDenied, Unauthenticated, DefaultCredentialsError):
            msg = f"GCP Secret Manager auth failed for {self.remote_address()}"
            raise PermissionError(msg) from None

        return self._nest_flat_keys(
            items,
            key_fn=lambda item: item[0],
            value_fn=lambda item: self._decode_raw(item[1]),
            separator=self.separator,
        )

    def _decodes_to_strings(self) -> bool:
        return self.decode == "utf-8"
