"""Unit tests for zookeeper_ module (ZookeeperSource).

Container-based integration tests live in ``tests/integration/sources/zookeeper/``.
"""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import kazoo.client
import kazoo.exceptions
import pytest

from dature import ZookeeperSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group
from dature.loading.source_validation import validate_source
from dature.sources.base import bytes_value_loaders, remote_value_loaders, string_value_loaders
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestZookeeperSourceDisplayProperties:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("format_name", "zookeeper", id="format_name"),
            pytest.param("location_label", "ZOOKEEPER", id="location_label"),
            pytest.param("config_group", "zookeeper", id="config_group"),
        ],
    )
    def test_class_attribute(self, attr, expected):
        assert getattr(ZookeeperSource, attr) == expected

    @pytest.mark.parametrize(
        ("decode", "expected"),
        [
            pytest.param("utf-8", string_value_loaders(), id="utf8"),
            pytest.param("json", remote_value_loaders(), id="json"),
            pytest.param("raw", bytes_value_loaders(), id="raw"),
        ],
    )
    def test_format_loaders(self, decode, expected):
        src = ZookeeperSource(hosts="zk1:2181", path="myapp", decode=decode)

        loaders = src.format_loaders()

        assert loaders == expected

    def test_format_loaders_raises_on_unknown_decode(self):
        src = ZookeeperSource(hosts="zk1:2181", path="myapp", decode="xml")

        with pytest.raises(ValueError, match="Unknown decode mode: 'xml'"):
            src.format_loaders()

    def test_decode_value_raises_on_unknown_decode(self):
        src = ZookeeperSource(hosts="zk1:2181", path="myapp", decode="xml")

        with pytest.raises(ValueError, match="Unknown decode mode: 'xml'"):
            src._decode_value(b"data")

    @pytest.mark.usefixtures("_reset_config")
    @pytest.mark.parametrize(
        ("hosts", "path", "expected"),
        [
            pytest.param("zk1:2181", "myapp/config", "zk://zk1:2181/myapp/config", id="string_form"),
            pytest.param(
                ["zk1:2181", "zk2:2181"],
                "myapp/config",
                "zk://zk1:2181,zk2:2181/myapp/config",
                id="list_form",
            ),
            pytest.param("zk1:2181/chroot", "myapp", "zk://zk1:2181/chroot/myapp", id="chroot_suffix"),
            pytest.param("zk1:2181", "/myapp", "zk://zk1:2181/myapp", id="leading_slash_not_doubled"),
            pytest.param(None, "myapp", "zk://localhost:2181/myapp", id="default_hosts_from_config"),
        ],
    )
    def test_remote_address(self, hosts, path, expected):
        kwargs = {"path": path}
        if hosts is not None:
            kwargs["hosts"] = hosts
        src = apply_source_config_group(ZookeeperSource(**kwargs))

        address = src.remote_address()

        assert address == expected


_HOSTS_FORMAT_ERROR = re.escape(
    "ZookeeperSource: hosts must be 'host:port' entries — a comma-separated string "
    "('zk1:2181,zk2:2181' or 'zk1:2181/myapp') or a list (['zk1:2181', 'zk2:2181'])"
)


@pytest.mark.usefixtures("_reset_config")
class TestZookeeperSourceValidation:
    @pytest.mark.parametrize(
        "hosts",
        [
            pytest.param("zk1", id="missing_port"),
            pytest.param("http://zk1:2181", id="scheme_not_allowed"),
            pytest.param("zk1:2181, zk2:2181", id="space_after_comma"),
            pytest.param(["zk1"], id="list_missing_port"),
            pytest.param(["zk1:2181", 5], id="list_non_string_item"),
            pytest.param(5, id="not_str_or_list"),
        ],
    )
    def test_hosts_format_raises_when_invalid(self, hosts):
        merged = apply_source_config_group(ZookeeperSource(path="p", hosts=hosts))

        with pytest.raises(ValueError, match=f"^{_HOSTS_FORMAT_ERROR}$"):
            validate_source(merged)

    @pytest.mark.parametrize(
        "hosts",
        [
            pytest.param("zk1:2181", id="single"),
            pytest.param("zk1:2181,zk2:2181", id="comma_separated"),
            pytest.param("zk1:2181/myapp", id="with_chroot"),
            pytest.param(["zk1:2181", "zk2:2181"], id="list"),
        ],
    )
    def test_hosts_format_passes_when_valid(self, hosts):
        merged = apply_source_config_group(ZookeeperSource(path="p", hosts=hosts))

        validate_source(merged)

    def test_no_hosts_raises(self):
        # ZookeeperConfig defaults hosts to "localhost:2181", so the fallback group always
        # fills it in — "hosts is required" is only reachable when validate_source() runs on
        # a bare instance that skipped the config-group merge (e.g. config_group=None).
        src = ZookeeperSource(path="p", config_group=None)

        with pytest.raises(ValueError, match="hosts is required"):
            validate_source(src)

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            pytest.param(
                {"user": "u"},
                "^ZookeeperSource: user and password must be set together$",
                id="user_without_password",
            ),
            pytest.param(
                {"password": "pw"},
                "^ZookeeperSource: user and password must be set together$",
                id="password_without_user",
            ),
            pytest.param(
                {"user": "u", "password": "pw", "sasl_options": {"mechanism": "DIGEST-MD5"}},
                re.escape("ZookeeperSource: digest auth (user/password) and sasl_options are mutually exclusive"),
                id="digest_and_sasl",
            ),
        ],
    )
    def test_validate_raises_when_invalid(self, kwargs, match):
        merged = apply_source_config_group(ZookeeperSource(path="p", hosts="zk1:2181", **kwargs))

        with pytest.raises(ValueError, match=match):
            validate_source(merged)

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({}, id="bare"),
            pytest.param({"user": "u", "password": "pw"}, id="user_and_password"),
            pytest.param({"sasl_options": {"mechanism": "GSSAPI"}}, id="sasl_options"),
        ],
    )
    def test_validate_passes(self, kwargs):
        merged = apply_source_config_group(ZookeeperSource(path="p", hosts="zk1:2181", **kwargs))

        validate_source(merged)


@pytest.mark.usefixtures("_reset_config")
class TestZookeeperSourceConfigFallback:
    def test_hosts_from_configure(self):
        configure(zookeeper={"hosts": "from-configure:2181", "user": "u", "password": "pw"})

        merged = apply_source_config_group(ZookeeperSource(path="p"))

        assert merged.hosts == "from-configure:2181"
        assert merged.user == "u"
        assert merged.password == "pw"

    def test_creds_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DATURE_ZOOKEEPER__HOSTS", "localhost:2181")
        monkeypatch.setenv("DATURE_ZOOKEEPER__USER", "root")
        monkeypatch.setenv("DATURE_ZOOKEEPER__PASSWORD", "root-pw")

        merged = apply_source_config_group(ZookeeperSource(path="myapp/config"))

        assert merged.hosts == "localhost:2181"
        assert merged.user == "root"
        assert merged.password == "root-pw"

    def test_instance_overrides_global(self):
        configure(zookeeper={"hosts": "global:2181", "user": "global-user", "password": "global-pw"})

        merged = apply_source_config_group(ZookeeperSource(path="p", hosts="instance:2181"))

        assert merged.hosts == "instance:2181"
        assert merged.user == "global-user"

    @pytest.mark.parametrize(
        ("hosts", "expected"),
        [
            # hosts=[] is the "unset" value for a str | list[str] field, same as "" for str fields.
            pytest.param([], "global:2181", id="empty_list_falls_through_to_config"),
            pytest.param(["instance:2181"], ["instance:2181"], id="non_empty_list_instance_wins"),
        ],
    )
    def test_list_hosts_fallback(self, hosts, expected):
        configure(zookeeper={"hosts": "global:2181"})

        merged = apply_source_config_group(ZookeeperSource(path="p", hosts=hosts))

        assert merged.hosts == expected

    @pytest.mark.parametrize(
        ("global_value", "instance_value", "expected"),
        [
            pytest.param(10.0, None, 10.0, id="timeout_from_global"),
            pytest.param(10.0, 20.0, 20.0, id="timeout_instance_wins"),
            pytest.param(None, None, None, id="timeout_default"),
        ],
    )
    def test_timeout_fallback(self, global_value, instance_value, expected):
        config_kwargs = {"hosts": "zk1:2181"}
        if global_value is not None:
            config_kwargs["timeout"] = global_value
        configure(zookeeper=config_kwargs)

        merged = apply_source_config_group(ZookeeperSource(path="p", timeout=instance_value))

        assert merged.timeout == expected


class FakeKazooClient:
    """Stand-in for ``kazoo.client.KazooClient``."""

    def __init__(
        self,
        tree: "dict[str, object] | None" = None,
        single: bytes | None = None,
        start_error: Exception | None = None,
        **kwargs: object,
    ) -> None:
        self.init_kwargs = kwargs
        self._tree = tree if tree is not None else {}
        self._single = single
        self._start_error = start_error
        self.started = False
        self.stopped = False
        self.closed = False
        self.start_kwargs: dict[str, float] | None = None

    def start(self, **kwargs: float) -> None:
        self.start_kwargs = kwargs
        if self._start_error is not None:
            raise self._start_error
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True

    def get_children(self, path: str) -> list[str]:
        node = self._resolve(path)
        if node is None or not isinstance(node, dict):
            return []
        return list(node.keys())

    def get(self, path: str) -> tuple[bytes, None]:
        if self._single is not None:
            return self._single, None
        node = self._resolve(path)
        if node is None or isinstance(node, dict):
            raise kazoo.exceptions.NoNodeError
        assert isinstance(node, bytes)
        return node, None

    def _resolve(self, path: str) -> object:
        parts = [p for p in path.split("/") if p]
        node: object = self._tree
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node


@dataclass
class _FetchConfig:
    port: int


class TestZookeeperSourceFetch:
    def _make_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        tree: "dict[str, object] | None" = None,
        single: bytes | None = None,
        start_error: Exception | None = None,
        **kwargs: object,
    ) -> ZookeeperSource:
        client_holder: dict[str, FakeKazooClient] = {}

        def _fake_client(**kw: object) -> FakeKazooClient:
            client = FakeKazooClient(tree=tree, single=single, start_error=start_error, **kw)
            client_holder["client"] = client
            return client

        monkeypatch.setattr(sys.modules["kazoo.client"], "KazooClient", _fake_client)
        kwargs.setdefault("path", "myapp")
        kwargs.setdefault("hosts", "zk1:2181")
        kwargs.setdefault("expand_env_vars", "default")
        src = ZookeeperSource(**kwargs)
        src._test_client_holder = client_holder
        return src

    def test_recursive_nests_on_separator(self, monkeypatch):
        tree = {"myapp": {"db": {"host": b"localhost", "port": b"5432"}, "name": b"svc"}}
        src = self._make_source(monkeypatch, tree=tree)

        result = src.load_raw()

        assert result.loaded_data == {
            "db": {"host": "localhost", "port": "5432"},
            "name": "svc",
        }

    def test_recursive_drops_data_on_znode_with_children(self, monkeypatch):
        # A znode that has both its own data AND children is treated as a pure intermediate
        # node — its own data is dropped, since _nest_flat_keys can't represent both a value
        # and a subtree under the same key.
        class NodeWithDataAndChildren(FakeKazooClient):
            def get_children(self, path):
                if path == "/myapp":
                    return ["name"]
                return []

            def get(self, path):
                if path == "/myapp":
                    return b"should-be-dropped", None
                if path == "/myapp/name":
                    return b"svc", None
                raise kazoo.exceptions.NoNodeError

        monkeypatch.setattr(sys.modules["kazoo.client"], "KazooClient", NodeWithDataAndChildren)
        src = ZookeeperSource(hosts="zk1:2181", path="myapp", expand_env_vars="default")

        result = src.load_raw()

        assert result.loaded_data == {"name": "svc"}

    def test_recursive_separator_none_keeps_flat_keys(self, monkeypatch):
        tree = {"myapp": {"db": {"host": b"localhost"}, "name": b"svc"}}
        src = self._make_source(monkeypatch, tree=tree, separator=None)

        result = src.load_raw()

        assert result.loaded_data == {
            "/db/host": "localhost",
            "/name": "svc",
        }

    @pytest.mark.parametrize(
        ("decode", "raw_value", "expected"),
        [
            pytest.param("utf-8", b"localhost", "localhost", id="utf8"),
            pytest.param("json", b'{"a": 1}', {"a": 1}, id="json"),
            pytest.param("raw", b"localhost", b"localhost", id="raw"),
        ],
    )
    def test_recursive_decode_modes(self, monkeypatch, decode, raw_value, expected):
        tree = {"myapp": {"host": raw_value}}
        src = self._make_source(monkeypatch, tree=tree, decode=decode)

        result = src.load_raw()

        assert result.loaded_data == {"host": expected}

    def test_single_node_json_becomes_root(self, monkeypatch):
        src = self._make_source(monkeypatch, single=b'{"db": {"host": "localhost"}}', recursive=False, decode="json")

        result = src.load_raw()

        assert result.loaded_data == {"db": {"host": "localhost"}}

    def test_single_node_non_json_uses_last_segment(self, monkeypatch):
        src = self._make_source(monkeypatch, single=b"svc", path="myapp/name", recursive=False)

        result = src.load_raw()

        assert result.loaded_data == {"name": "svc"}

    def test_missing_node_raises_key_error(self, monkeypatch):
        src = self._make_source(monkeypatch, tree={})

        with pytest.raises(KeyError, match="Zookeeper znode not found"):
            src.load_raw()

    def test_missing_single_node_raises_key_error(self, monkeypatch):
        class MissingNodeClient(FakeKazooClient):
            def get(self, path):  # noqa: ARG002
                raise kazoo.exceptions.NoNodeError

        monkeypatch.setattr(sys.modules["kazoo.client"], "KazooClient", MissingNodeClient)
        src = ZookeeperSource(hosts="zk1:2181", path="myapp", recursive=False)

        with pytest.raises(KeyError, match="Zookeeper znode not found"):
            src.load_raw()

    def test_comprehensive_type_conversion(self, monkeypatch, all_types_zookeeper_kv_file: Path):
        """Loading a recursive ZooKeeper subtree (decode='utf-8') with full type coercion."""
        kv_map = json.loads(all_types_zookeeper_kv_file.read_text())
        tree: dict[str, object] = {}
        for key, value in kv_map.items():
            parts = key.replace("all_types", "myapp", 1).split("/")
            node: dict[str, object] = tree
            for part in parts[:-1]:
                node = cast("dict[str, object]", node.setdefault(part, {}))
            node[parts[-1]] = value.encode("utf-8")
        src = self._make_source(monkeypatch, tree=tree)

        result = load(src, schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_missing_node_error_message_includes_path(self, monkeypatch):
        self._make_source(monkeypatch, tree={})

        with pytest.raises(DatureConfigError) as exc_info:
            load(ZookeeperSource(hosts="zk1:2181", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == "'Zookeeper znode not found: zk://zk1:2181/myapp'"

    def test_bad_type_error_message_includes_path_and_value(self, monkeypatch):
        tree = {"myapp": {"port": b"not_a_number"}}
        self._make_source(monkeypatch, tree=tree)

        with pytest.raises(DatureConfigError) as exc_info:
            load(ZookeeperSource(hosts="zk1:2181", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "  [port]  invalid literal for int() with base 10: '<REDACTED>'\n"
            "   ├── zk://zk1:2181/myapp: port = <REDACTED>\n"
            "   │                               ^^^^^^^^^^"
        )

    def test_raw_decode_loads_into_bytes_field(self, monkeypatch):
        tree = {"myapp": {"blob": b"\x00\x01raw"}}
        self._make_source(monkeypatch, tree=tree, decode="raw")

        @dataclass
        class Config:
            blob: bytes

        result = load(ZookeeperSource(hosts="zk1:2181", path="myapp", decode="raw"), schema=Config)

        assert result == Config(blob=b"\x00\x01raw")

    @pytest.mark.parametrize(
        "start_error",
        [
            pytest.param(kazoo.exceptions.NoAuthError(), id="no_auth_error"),
            pytest.param(kazoo.exceptions.AuthFailedError(), id="auth_failed_error"),
        ],
    )
    def test_auth_error_raises_permission_error(self, monkeypatch, start_error):
        self._make_source(monkeypatch, tree={}, start_error=start_error)
        src = ZookeeperSource(hosts="zk1:2181", path="myapp")

        with pytest.raises(PermissionError, match="Zookeeper auth failed"):
            src.load_raw()

    def test_other_kazoo_exception_propagates(self, monkeypatch):
        self._make_source(monkeypatch, tree={}, start_error=kazoo.exceptions.ConnectionLoss())
        src = ZookeeperSource(hosts="zk1:2181", path="myapp")

        with pytest.raises(kazoo.exceptions.ConnectionLoss):
            src.load_raw()

    def test_client_closed_on_error_path(self, monkeypatch):
        src = self._make_source(monkeypatch, tree={}, start_error=kazoo.exceptions.NoAuthError())

        with pytest.raises(PermissionError):
            src.load_raw()

        assert src._test_client_holder["client"].stopped
        assert src._test_client_holder["client"].closed

    def test_hosts_list_joined_for_client(self, monkeypatch):
        src = self._make_source(monkeypatch, tree={"myapp": {"name": b"svc"}}, hosts=["zk1:2181", "zk2:2181"])

        src.load_raw()

        assert src._test_client_holder["client"].init_kwargs["hosts"] == "zk1:2181,zk2:2181"

    def test_digest_auth_data_forwarded(self, monkeypatch):
        src = self._make_source(monkeypatch, tree={"myapp": {"name": b"svc"}}, user="root", password="root-pw")

        src.load_raw()

        assert src._test_client_holder["client"].init_kwargs["auth_data"] == [("digest", "root:root-pw")]

    def test_sasl_options_forwarded(self, monkeypatch):
        sasl_options = {"mechanism": "GSSAPI"}
        src = self._make_source(monkeypatch, tree={"myapp": {"name": b"svc"}}, sasl_options=sasl_options)

        src.load_raw()

        assert src._test_client_holder["client"].init_kwargs["sasl_options"] == sasl_options
        assert src._test_client_holder["client"].init_kwargs["auth_data"] is None

    @pytest.mark.parametrize(
        ("timeout", "expected_session_timeout"),
        [
            pytest.param(None, 10.0, id="default_session_timeout"),
            pytest.param(30.0, 30.0, id="explicit_session_timeout"),
        ],
    )
    def test_session_timeout_forwarded(self, monkeypatch, timeout, expected_session_timeout):
        src = self._make_source(monkeypatch, tree={"myapp": {"name": b"svc"}}, timeout=timeout)

        src.load_raw()

        assert src._test_client_holder["client"].init_kwargs["timeout"] == expected_session_timeout

    def test_connection_timeout_forwarded_to_start(self, monkeypatch):
        src = self._make_source(monkeypatch, tree={"myapp": {"name": b"svc"}}, connection_timeout=5.0)

        src.load_raw()

        assert src._test_client_holder["client"].start_kwargs == {"timeout": 5.0}

    def test_no_connection_timeout_uses_kazoo_default(self, monkeypatch):
        src = self._make_source(monkeypatch, tree={"myapp": {"name": b"svc"}})

        src.load_raw()

        assert src._test_client_holder["client"].start_kwargs == {}


@pytest.mark.usefixtures("_reset_config")
def test_missing_kazoo_raises_on_load(block_import, monkeypatch):
    """`import dature` works without kazoo; only _fetch() requires it."""
    monkeypatch.setenv("DATURE_ZOOKEEPER__HOSTS", "zk1:2181")

    @dataclass
    class Config:
        foo: str = ""

    with block_import("kazoo"), pytest.raises(DatureConfigError) as exc_info:
        load(ZookeeperSource(path="p"), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == "'kazoo' is not installed. Run: pip install 'dature[zookeeper]'"
