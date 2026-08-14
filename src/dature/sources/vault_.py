from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal, cast

from dature._deps import require_dep
from dature.sources.base import RemoteSource
from dature.type_aliases import JSONValue
from dature.validators.root import RootPredicate
from dature.validators.v import V


@dataclass(kw_only=True, repr=False)
class VaultSource(RemoteSource):
    path: str

    host: Annotated[
        str,
        (V.len() >= 1).with_error_message(
            "host is required (set on instance or via configure(vault={...}) / DATURE_VAULT__HOST)"
        ),
    ] = ""
    port: Annotated[int | None, (V > 0).with_error_message("port must be a positive integer")] = None
    scheme: Literal["http", "https"] | None = None
    mount_point: str = ""
    kv_version: Literal[1, 2] | None = None
    token: str | None = None
    role_id: str | None = None
    secret_id: str | None = None
    namespace: str | None = None
    verify: bool | str | None = None

    format_name: str = "vault"
    location_label: str = "VAULT"
    config_group: str | None = "vault"

    root_validators: ClassVar[tuple[RootPredicate, ...]] = (
        V.root(
            lambda s: s.token is None or (s.role_id is None and s.secret_id is None),
            error_message="token and role_id/secret_id are mutually exclusive",
        ),
        V.root(
            lambda s: s.token is not None or (s.role_id is not None and s.secret_id is not None),
            error_message="requires either token or role_id+secret_id",
        ),
    )

    def _base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    def remote_address(self) -> str:
        match self.kv_version:
            case 1:
                infix = ""
            case 2 | None:
                infix = "data/"
            case _ as unknown:
                msg = f"Unknown kv_version: {unknown!r}"
                raise ValueError(msg)
        return f"{self._base_url()}/v1/{self.mount_point}/{infix}{self.path}"

    def _fetch(self) -> JSONValue:
        require_dep("hvac", "vault")
        import hvac  # noqa: PLC0415
        import hvac.exceptions  # noqa: PLC0415

        client = hvac.Client(url=self._base_url(), namespace=self.namespace, verify=self.verify)
        if self.token is not None:
            client.token = self.token
        else:
            client.auth.approle.login(role_id=self.role_id, secret_id=self.secret_id)

        try:
            match self.kv_version:
                case 1:
                    resp = client.secrets.kv.v1.read_secret(path=self.path, mount_point=self.mount_point)
                    return cast("JSONValue", resp["data"])
                case 2 | None:
                    resp = client.secrets.kv.v2.read_secret_version(path=self.path, mount_point=self.mount_point)
                    return cast("JSONValue", resp["data"]["data"])
                case _ as unknown:
                    msg = f"Unknown kv_version: {unknown!r}"
                    raise ValueError(msg)
        except hvac.exceptions.InvalidPath:
            msg = f"Vault path not found: {self.remote_address()}"
            raise KeyError(msg) from None
        except (hvac.exceptions.Forbidden, hvac.exceptions.Unauthorized):
            msg = f"Vault auth failed for {self._base_url()}"
            raise PermissionError(msg) from None
