import json
from dataclasses import dataclass
from typing import Annotated, Any, Literal, cast

from adaptix.provider import Provider

from dature._deps import require_dep
from dature.sources.base import RemoteSource, bytes_value_loaders, string_value_loaders
from dature.type_aliases import JSONValue
from dature.validators.v import V


@dataclass(kw_only=True, repr=False)
class ConsulSource(RemoteSource):
    path: str
    """KV key (``recursive=False``) or prefix (``recursive=True``) inside Consul's KV store."""

    host: Annotated[
        str,
        (V.len() >= 1).with_error_message(
            "host is required (set on instance or via configure(consul={...}) / DATURE_CONSUL__HOST)"
        ),
    ] = ""
    port: Annotated[int | None, (V > 0).with_error_message("port must be a positive integer")] = None
    scheme: Literal["http", "https"] | None = None
    token: str | None = None
    datacenter: str | None = None
    verify: bool | str | None = None
    recursive: bool = True
    decode: Literal["utf-8", "json", "raw"] = "utf-8"
    separator: str | None = "/"

    format_name: str = "consul"
    location_label: str = "CONSUL"
    config_group: str | None = "consul"

    def remote_address(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}/v1/kv/{self.path}"

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

    def _decode_value(self, raw: "bytes | None") -> JSONValue:
        if raw is None:
            # A live Consul agent reports "Value": null for a key stored with an empty
            # value (0 bytes), indistinguishable at this point from a genuine directory
            # marker. For decode="utf-8" the empty-bytes reading is "" — consistent with
            # how every other flat-key source represents an empty value, and letting
            # ``none_from_empty_string`` (in string_value_loaders) turn it into None when
            # the target field is Optional/None-typed.
            return "" if self.decode == "utf-8" else None
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

    def _build_single(self, item: "dict[str, Any]") -> JSONValue:
        value = self._decode_value(item.get("Value"))
        if self.decode == "json":
            # The single key holds the entire config document — it *is* the root, not a leaf.
            return value
        key = cast("str", item["Key"])
        last_segment = key.rsplit(self.separator, 1)[-1] if self.separator else key
        return {last_segment: value}

    def _fetch(self) -> JSONValue:
        require_dep("consul", "consul")
        # py-consul's __init__.py re-exports these without __all__, which mypy's
        # no_implicit_reexport (part of strict=true) rejects — import from the
        # defining submodules directly instead.
        from consul.exceptions import ACLDisabled, ACLPermissionDenied  # noqa: PLC0415
        from consul.std import Consul  # noqa: PLC0415

        client = Consul(
            host=self.host,
            port=self.port,
            scheme=self.scheme,
            token=self.token,
            dc=self.datacenter,
            verify=self.verify,
        )

        try:
            _index, data = client.kv.get(self.path, recurse=self.recursive)
        except (ACLPermissionDenied, ACLDisabled):
            msg = f"Consul auth failed for {self.remote_address()}"
            raise PermissionError(msg) from None

        if data is None:
            msg = f"Consul key not found: {self.remote_address()}"
            raise KeyError(msg) from None

        if self.recursive:
            result: JSONValue = self._nest_flat_keys(
                cast("list[dict[str, Any]]", data),
                key_fn=lambda i: cast("str", i["Key"]),
                value_fn=lambda i: self._decode_value(i.get("Value")),
                prefix=self.path,
                separator=self.separator,
            )
        else:
            result = self._build_single(cast("dict[str, Any]", data))

        return result

    def _decodes_to_strings(self) -> bool:
        return self.decode == "utf-8"
