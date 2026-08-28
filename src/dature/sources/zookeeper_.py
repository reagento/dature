"""ZookeeperSource: loads configuration from an Apache ZooKeeper znode tree."""

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Final, Literal, cast

from adaptix.provider import Provider

from dature._deps import require_dep
from dature.sources.base import RemoteSource, bytes_value_loaders, string_value_loaders
from dature.type_aliases import JSONValue
from dature.validators.root import RootPredicate
from dature.validators.v import V

_HOST_PORT_RE: Final = re.compile(r"^[\w.\-\[\]]+:\d{1,5}$")


def _valid_hosts(value: object) -> bool:
    """Whether *value* is a valid ``hosts``: ``host:port`` entries as a comma-separated
    string (with an optional trailing ``/chroot``) or as a list.

    Empty (``""`` / ``[]``) passes — required-ness is enforced separately by a root
    validator so the two failure modes get distinct messages.
    """
    if isinstance(value, str):
        if not value:
            return True
        entries = value.split("/", 1)[0].split(",")
    elif isinstance(value, list):
        if not value:
            return True
        if not all(isinstance(item, str) for item in value):
            return False
        entries = value
    else:
        return False
    return all(_HOST_PORT_RE.match(entry) for entry in entries)


_HOSTS_ERROR: Final = (
    "hosts must be 'host:port' entries — a comma-separated string "
    "('zk1:2181,zk2:2181' or 'zk1:2181/myapp') or a list (['zk1:2181', 'zk2:2181'])"
)


@dataclass(kw_only=True, repr=False)
class ZookeeperSource(RemoteSource):
    path: str
    """ZooKeeper znode (``recursive=False``) or subtree root (``recursive=True``)."""

    hosts: Annotated[
        "str | list[str]",
        V.check(_valid_hosts, error_message=_HOSTS_ERROR),
    ] = ""
    """Ensemble address(es): ``"zk1:2181,zk2:2181"`` or ``["zk1:2181", "zk2:2181"]``.

    The string form may carry an optional trailing ``/chroot`` (kazoo's own convention);
    the list form does not.
    """
    user: str | None = None
    password: str | None = None
    sasl_options: "dict[str, str] | None" = None
    timeout: float | None = None
    """ZooKeeper session timeout in seconds. ``None`` uses kazoo's own default (10s)."""
    connection_timeout: float | None = None
    """How long to wait for the initial connection in seconds. ``None`` uses kazoo's own
    default (15s)."""
    recursive: bool = True
    decode: Literal["utf-8", "json", "raw"] = "utf-8"
    separator: str | None = "/"

    format_name: str = "zookeeper"
    location_label: str = "ZOOKEEPER"
    config_group: str | None = "zookeeper"

    root_validators: ClassVar[tuple[RootPredicate, ...]] = (
        V.root(
            lambda s: bool(s.hosts),
            error_message=(
                "hosts is required (set on instance or via configure(zookeeper={...}) / DATURE_ZOOKEEPER__HOSTS)"
            ),
        ),
        V.root(
            lambda s: (s.user is None) == (s.password is None),
            error_message="user and password must be set together",
        ),
        V.root(
            lambda s: s.sasl_options is None or (s.user is None and s.password is None),
            error_message="digest auth (user/password) and sasl_options are mutually exclusive",
        ),
    )

    def _hosts_str(self) -> str:
        """kazoo's native ``"host:port,host:port[/chroot]"`` form of ``hosts``."""
        return ",".join(self.hosts) if isinstance(self.hosts, list) else self.hosts

    def _root_path(self) -> str:
        return self.path if self.path.startswith("/") else f"/{self.path}"

    def remote_address(self) -> str:
        return f"zk://{self._hosts_str()}{self._root_path()}"

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

    def _build_single(self, path: str, value: bytes) -> JSONValue:
        decoded = self._decode_value(value)
        if self.decode == "json":
            # The single znode holds the entire config document — it *is* the root, not a leaf.
            return decoded
        last_segment = path.rsplit(self.separator, 1)[-1] if self.separator else path
        return {last_segment: decoded}

    def _walk(self, client: Any, root: str) -> "list[tuple[str, bytes]]":  # noqa: ANN401
        """Depth-first collect ``(znode_path, data)`` for every *leaf* znode under *root*.

        A znode that has children is treated as a pure intermediate node — its own data,
        if any, is dropped, since ``_nest_flat_keys`` cannot represent both a value and a
        subtree under the same key.
        """
        items: list[tuple[str, bytes]] = []
        stack = [root]
        while stack:
            node = stack.pop()
            children = client.get_children(node)
            if not children:
                data, _ = client.get(node)
                # ``client.get`` always returns bytes for an existing leaf znode (raising
                # NoNodeError otherwise) — an empty value (b"") is a legitimate leaf, e.g. an
                # empty-string config field, and must not be dropped here.
                items.append((node, data))
                continue
            base = node if node != "/" else ""
            stack.extend(f"{base}/{child}" for child in children)
        return items

    @contextmanager
    def _connect(self) -> "Iterator[Any]":
        """Yield a started ``KazooClient``, always tearing the session down afterwards."""
        from kazoo.client import KazooClient  # noqa: PLC0415

        client = KazooClient(  # type: ignore[no-untyped-call]
            hosts=self._hosts_str(),
            timeout=self.timeout if self.timeout is not None else 10.0,
            auth_data=[("digest", f"{self.user}:{self.password}")] if self.user is not None else None,
            sasl_options=self.sasl_options,
        )
        start_kwargs = {} if self.connection_timeout is None else {"timeout": self.connection_timeout}
        try:
            client.start(**start_kwargs)  # type: ignore[no-untyped-call]
            yield client
        finally:
            client.stop()  # type: ignore[no-untyped-call]
            client.close()  # type: ignore[no-untyped-call]

    def _fetch(self) -> JSONValue:
        require_dep("kazoo", "zookeeper")
        from kazoo.exceptions import AuthFailedError, NoAuthError, NoNodeError  # noqa: PLC0415

        root = self._root_path()
        try:
            with self._connect() as client:
                if not self.recursive:
                    data, _ = client.get(root)
                    return self._build_single(root, data)
                return self._nest_flat_keys(
                    self._walk(client, root),
                    key_fn=lambda item: item[0],
                    value_fn=lambda item: self._decode_value(item[1]),
                    prefix=root,
                    separator=self.separator,
                )
        except NoNodeError:
            msg = f"Zookeeper znode not found: {self.remote_address()}"
            raise KeyError(msg) from None
        except (NoAuthError, AuthFailedError):
            msg = f"Zookeeper auth failed for {self.remote_address()}"
            raise PermissionError(msg) from None

    def _decodes_to_strings(self) -> bool:
        return self.decode == "utf-8"
