from dataclasses import dataclass
from typing import ClassVar, Literal, cast

from dature._deps import require_dep
from dature.sources.remote import RemoteSource
from dature.type_aliases import JSONValue


@dataclass(kw_only=True, repr=False)
class VaultSource(RemoteSource):
    path: str

    url: str | None = None
    mount_point: str | None = None
    kv_version: Literal[1, 2] | None = None
    token: str | None = None
    role_id: str | None = None
    secret_id: str | None = None
    namespace: str | None = None
    verify: bool | str | None = None

    format_name = "vault"
    location_label: ClassVar[str] = "VAULT"
    config_group: ClassVar[str | None] = "vault"

    def remote_address(self) -> str:
        if self.kv_version == 1:
            return f"{self.url}/v1/{self.mount_point}/{self.path}"
        return f"{self.url}/v1/{self.mount_point}/data/{self.path}"

    def check_invariants(self) -> None:
        if self.token is not None and (self.role_id is not None or self.secret_id is not None):
            msg = "VaultSource: token and role_id/secret_id are mutually exclusive"
            raise ValueError(msg)
        if self.url is None:
            msg = "VaultSource: url is required (set on instance or via configure(vault={...}) / DATURE_VAULT__URL)"
            raise ValueError(msg)
        has_token = self.token is not None
        has_role_id = self.role_id is not None
        has_secret_id = self.secret_id is not None
        if not has_token and not (has_role_id and has_secret_id):
            msg = "VaultSource: requires either token or role_id+secret_id"
            raise ValueError(msg)

    def _fetch(self) -> JSONValue:
        require_dep("hvac", "vault")
        import hvac  # noqa: PLC0415
        import hvac.exceptions  # noqa: PLC0415

        client = hvac.Client(url=self.url, namespace=self.namespace, verify=self.verify)
        if self.token is not None:
            client.token = self.token
        else:
            client.auth.approle.login(role_id=self.role_id, secret_id=self.secret_id)

        try:
            if self.kv_version == 1:
                resp = client.secrets.kv.v1.read_secret(path=self.path, mount_point=self.mount_point)
                return cast("JSONValue", resp["data"])
            resp = client.secrets.kv.v2.read_secret_version(path=self.path, mount_point=self.mount_point)
            return cast("JSONValue", resp["data"]["data"])
        except hvac.exceptions.InvalidPath:
            msg = f"Vault path not found: {self.remote_address()}"
            raise KeyError(msg) from None
        except (hvac.exceptions.Forbidden, hvac.exceptions.Unauthorized):
            msg = f"Vault auth failed for {self.url}"
            raise PermissionError(msg) from None
