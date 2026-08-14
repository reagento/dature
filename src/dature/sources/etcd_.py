import json
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Literal, cast

from adaptix.provider import Provider

from dature._deps import require_dep
from dature.sources.base import RemoteSource, bytes_value_loaders, string_value_loaders
from dature.type_aliases import JSONValue
from dature.validators.root import RootPredicate
from dature.validators.v import V


@dataclass(kw_only=True, repr=False)
class EtcdSource(RemoteSource):
    path: str
    """etcd key (``recursive=False``) or prefix (``recursive=True``)."""

    host: Annotated[
        str,
        (V.len() >= 1).with_error_message(
            "host is required (set on instance or via configure(etcd={...}) / DATURE_ETCD__HOST)"
        ),
    ] = ""
    port: Annotated[int | None, (V > 0).with_error_message("port must be a positive integer")] = None
    protocol: Literal["http", "https"] | None = None
    user: str | None = None
    password: str | None = None
    ca_cert: str | None = None
    cert_cert: str | None = None
    cert_key: str | None = None
    timeout: float | None = None
    recursive: bool = True
    decode: Literal["utf-8", "json", "raw"] = "utf-8"
    separator: str | None = "/"

    format_name: str = "etcd"
    location_label: str = "ETCD"
    config_group: str | None = "etcd"

    root_validators: ClassVar[tuple[RootPredicate, ...]] = (
        V.root(
            lambda s: (s.user is None) == (s.password is None),
            error_message="user and password must be set together",
        ),
    )

    def remote_address(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}/v3/kv/{self.path}"

    def format_loaders(self) -> "list[Provider]":
        match self.decode:
            case "raw":
                return bytes_value_loaders()
            case "utf-8":
                return string_value_loaders()
            case "json":
                return super().format_loaders()
            case _ as unknown:
                msg = f"Unknown decode mode: {unknown!r}"
                raise ValueError(msg)

    def _decode_value(self, raw: bytes) -> JSONValue:
        match self.decode:
            case "raw":
                return cast("JSONValue", raw)
            case "json":
                return cast("JSONValue", json.loads(raw))
            case "utf-8":
                return raw.decode("utf-8")
            case _ as unknown:
                msg = f"Unknown decode mode: {unknown!r}"
                raise ValueError(msg)

    def _build_nested(self, items: "list[tuple[bytes, dict[str, object]]]") -> JSONValue:
        """Turn a recursive prefix listing into a nested dict, splitting each key on ``separator``.

        The prefix (``self.path``) is stripped from every key first. A key that matches the
        prefix exactly has no remainder and is dropped — it has no leaf name to store a value
        under.
        """
        root: dict[str, JSONValue] = {}
        for value, metadata in items:
            key = cast("bytes", metadata["key"]).decode("utf-8")
            remainder = key.removeprefix(self.path)
            if self.separator:
                remainder = remainder.lstrip(self.separator)
            if not remainder:
                continue
            parts = remainder.split(self.separator) if self.separator else [remainder]
            node = root
            for part in parts[:-1]:
                node = cast("dict[str, JSONValue]", node.setdefault(part, {}))
            node[parts[-1]] = self._decode_value(value)
        return root

    def _build_single(self, key: str, value: bytes) -> JSONValue:
        decoded = self._decode_value(value)
        if self.decode == "json":
            # The single key holds the entire config document — it *is* the root, not a leaf.
            return decoded
        last_segment = key.rsplit(self.separator, 1)[-1] if self.separator else key
        return {last_segment: decoded}

    def _authenticate(self, client: Any) -> None:  # noqa: ANN401
        """Set the RBAC token header on ``client``'s session, if credentials are configured.

        ``etcd3gw`` has no built-in auth support, but its ``post`` helper already handles
        timeouts and error mapping, so only the token exchange itself is ours.
        """
        if self.user is None:
            return

        resp = client.post(
            client.get_url("/auth/authenticate"),
            json={"name": self.user, "password": self.password},
        )
        token = resp.get("token")
        if not token:
            msg = f"etcd auth failed for {self.remote_address()}"
            raise PermissionError(msg)
        client.session.headers["Authorization"] = token

    def _fetch(self) -> JSONValue:
        require_dep("etcd3gw", "etcd")
        from etcd3gw.client import Etcd3Client  # noqa: PLC0415
        from etcd3gw.exceptions import Etcd3Exception  # noqa: PLC0415

        client_kwargs: dict[str, Any] = {
            "host": self.host,
            "ca_cert": self.ca_cert,
            "cert_cert": self.cert_cert,
            "cert_key": self.cert_key,
            "timeout": self.timeout,
        }
        if self.port is not None:
            client_kwargs["port"] = self.port
        if self.protocol is not None:
            client_kwargs["protocol"] = self.protocol
        client = Etcd3Client(**client_kwargs)

        try:
            self._authenticate(client)
            if self.recursive:
                items = cast("list[tuple[bytes, dict[str, object]]]", client.get_prefix(self.path))
                result = self._build_nested(items)
                found = bool(items)
            else:
                values = client.get(self.path)
                found = bool(values)
                result = self._build_single(self.path, values[0]) if found else {}
        except Etcd3Exception as exc:
            # etcd3gw has no dedicated permission-denied exception class — a missing or
            # invalid token surfaces here as a bare Etcd3Exception. etcd's gRPC-gateway maps
            # auth failures to varying HTTP status text/body ("401 Unauthorized", "403
            # Forbidden", or a "400 Bad Request" whose body says e.g. "authentication failed"
            # / "user name is empty"), so match on the body text rather than the status alone.
            reason = f"{exc.detail_text} {exc}".lower()
            auth_failure_markers = (
                "unauthorized",
                "forbidden",
                "permission denied",
                "authentication failed",
                "authentication is required",
                "invalid user",
                "invalid password",
                "user name is empty",
                "user name and password required",
            )
            if any(marker in reason for marker in auth_failure_markers):
                msg = f"etcd auth failed for {self.remote_address()}"
                raise PermissionError(msg) from None
            raise

        if not found:
            msg = f"etcd key not found: {self.remote_address()}"
            raise KeyError(msg) from None

        if self.decode == "utf-8":
            return self._parse_string_values(result)
        return result
