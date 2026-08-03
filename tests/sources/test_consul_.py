"""Unit tests for consul_ module (ConsulSource).

Container-based integration tests live in ``tests/integration/sources/consul/``.
"""

from dataclasses import dataclass

import consul.exceptions
import consul.std
import pytest

from dature import ConsulSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group


class TestConsulSourceDisplayProperties:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("format_name", "consul", id="format_name"),
            pytest.param("location_label", "CONSUL", id="location_label"),
            pytest.param("config_group", "consul", id="config_group"),
        ],
    )
    def test_class_attribute(self, attr, expected):
        assert getattr(ConsulSource, attr) == expected

    @pytest.mark.parametrize(
        ("scheme", "host", "port", "path", "expected"),
        [
            pytest.param("https", "c", 8500, "myapp/config", "https://c:8500/v1/kv/myapp/config", id="explicit"),
            pytest.param(None, "c", None, "myapp/config", "http://c:8500/v1/kv/myapp/config", id="default_scheme_port"),
            pytest.param("http", "", None, "p", "http://localhost:8500/v1/kv/p", id="default_host"),
        ],
    )
    def test_remote_address(self, scheme, host, port, path, expected):
        src = ConsulSource(host=host, port=port, scheme=scheme, path=path)
        assert src.remote_address() == expected


@pytest.mark.usefixtures("_reset_config")
class TestConsulSourceValidation:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            pytest.param({"path": "p", "host": "c", "scheme": "ftp"}, "scheme must be", id="bad_scheme"),
            pytest.param({"path": "p", "host": "c", "decode": "xml"}, "decode must be", id="bad_decode"),
            pytest.param({"path": "p", "host": "c", "port": 0}, "port must be", id="zero_port"),
            pytest.param({"path": "p", "host": "c", "port": -1}, "port must be", id="negative_port"),
        ],
    )
    def test_validate_raises_when_invalid(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            apply_source_config_group(ConsulSource(**kwargs)).check_invariants()

    def test_no_host_raises(self):
        # ConsulConfig defaults host to "localhost", so the fallback group always fills it in
        # — "host is required" is only reachable when check_invariants() runs on a bare instance
        # that skipped the config-group merge (e.g. config_group=None).
        with pytest.raises(ValueError, match="host is required"):
            ConsulSource(path="p").check_invariants()

    def test_validate_passes(self):
        merged = apply_source_config_group(ConsulSource(path="p", host="c"))
        merged.check_invariants()


@pytest.mark.usefixtures("_reset_config")
class TestConsulSourceConfigFallback:
    def test_host_from_configure(self):
        configure(consul={"host": "from-configure", "token": "t"})
        merged = apply_source_config_group(ConsulSource(path="p"))
        assert merged.host == "from-configure"
        assert merged.token == "t"

    def test_creds_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DATURE_CONSUL__HOST", "localhost")
        monkeypatch.setenv("DATURE_CONSUL__TOKEN", "root")
        merged = apply_source_config_group(ConsulSource(path="myapp/config"))
        assert merged.host == "localhost"
        assert merged.token == "root"

    def test_instance_overrides_global(self):
        configure(consul={"host": "global", "token": "global-token"})
        merged = apply_source_config_group(ConsulSource(path="p", host="instance"))
        assert merged.host == "instance"
        assert merged.token == "global-token"

    @pytest.mark.parametrize(
        ("global_value", "instance_value", "expected"),
        [
            pytest.param(8500, None, 8500, id="port_from_global"),
            pytest.param(8500, 8600, 8600, id="port_instance_wins"),
            pytest.param(None, None, 8500, id="port_default"),
        ],
    )
    def test_port_fallback(self, global_value, instance_value, expected):
        config_kwargs = {"host": "c"}
        if global_value is not None:
            config_kwargs["port"] = global_value
        configure(consul=config_kwargs)
        merged = apply_source_config_group(ConsulSource(path="p", port=instance_value))
        assert merged.port == expected

    @pytest.mark.parametrize(
        ("global_value", "instance_value", "expected"),
        [
            pytest.param("https", None, "https", id="scheme_from_global"),
            pytest.param("https", "http", "http", id="scheme_instance_wins"),
            pytest.param(None, None, "http", id="scheme_default"),
        ],
    )
    def test_scheme_fallback(self, global_value, instance_value, expected):
        config_kwargs = {"host": "c"}
        if global_value is not None:
            config_kwargs["scheme"] = global_value
        configure(consul=config_kwargs)
        merged = apply_source_config_group(ConsulSource(path="p", scheme=instance_value))
        assert merged.scheme == expected


class FakeKV:
    """Stand-in for py-consul's ``consul.Consul().kv``."""

    def __init__(self, data: object) -> None:
        self._data = data

    def get(self, path: str, *, recurse: bool = False) -> tuple[int, object]:  # noqa: ARG002
        return 0, self._data


class FakeConsul:
    def __init__(self, data: object, **kwargs: object) -> None:  # noqa: ARG002
        self.kv = FakeKV(data)


@dataclass
class _FetchConfig:
    port: int


class TestConsulSourceFetch:
    def _make_source(self, monkeypatch: pytest.MonkeyPatch, data: object, **kwargs: object) -> ConsulSource:
        def _fake_consul(**kw: object) -> FakeConsul:
            return FakeConsul(data, **kw)

        monkeypatch.setattr(consul.std, "Consul", _fake_consul)
        return ConsulSource(host="c", path="myapp", **kwargs)

    def test_recursive_nests_on_separator(self, monkeypatch):
        data = [
            {"Key": "myapp/db/host", "Value": b"localhost"},
            {"Key": "myapp/db/port", "Value": b"5432"},
            {"Key": "myapp/name", "Value": b"svc"},
        ]
        src = self._make_source(monkeypatch, data)
        assert src.load_raw().loaded_data == {
            "db": {"host": "localhost", "port": "5432"},
            "name": "svc",
        }

    def test_recursive_drops_directory_marker(self, monkeypatch):
        # Consul writes a key equal to the prefix itself (with Value=None) when the
        # prefix was created as a "directory" — it has no leaf name, so it's dropped.
        data = [
            {"Key": "myapp", "Value": None},
            {"Key": "myapp/name", "Value": b"svc"},
        ]
        src = self._make_source(monkeypatch, data)
        assert src.load_raw().loaded_data == {"name": "svc"}

    def test_recursive_separator_none_keeps_flat_keys(self, monkeypatch):
        data = [
            {"Key": "myapp/db/host", "Value": b"localhost"},
            {"Key": "myapp/name", "Value": b"svc"},
        ]
        src = self._make_source(monkeypatch, data, separator=None)
        assert src.load_raw().loaded_data == {
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
        data = [{"Key": "myapp/host", "Value": raw_value}]
        src = self._make_source(monkeypatch, data, decode=decode)
        assert src.load_raw().loaded_data == {"host": expected}

    def test_single_key_json_becomes_root(self, monkeypatch):
        item = {"Key": "myapp", "Value": b'{"db": {"host": "localhost"}}'}
        src = self._make_source(monkeypatch, item, recursive=False, decode="json")
        assert src.load_raw().loaded_data == {"db": {"host": "localhost"}}

    def test_single_key_non_json_uses_last_segment(self, monkeypatch):
        item = {"Key": "myapp/name", "Value": b"svc"}
        src = self._make_source(monkeypatch, item, recursive=False)
        assert src.load_raw().loaded_data == {"name": "svc"}

    def test_missing_key_raises_key_error(self, monkeypatch):
        src = self._make_source(monkeypatch, None)
        with pytest.raises(KeyError, match="Consul key not found"):
            src.load_raw()

    def test_missing_key_error_message_includes_path(self, monkeypatch):
        self._make_source(monkeypatch, None)

        with pytest.raises(DatureConfigError) as exc_info:
            load(ConsulSource(host="c", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == "'Consul key not found: http://c:8500/v1/kv/myapp'"

    def test_bad_type_error_message_includes_path_and_value(self, monkeypatch):
        data = [{"Key": "myapp/port", "Value": b"not_a_number"}]
        self._make_source(monkeypatch, data)

        with pytest.raises(DatureConfigError) as exc_info:
            load(ConsulSource(host="c", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "  [port]  invalid literal for int() with base 10: 'not_a_number'\n"
            "   ├── http://c:8500/v1/kv/myapp: port = not_a_number"
        )

    def test_acl_permission_denied_raises_permission_error(self, monkeypatch):
        class DeniedKV:
            def get(self, path, *, recurse=False):  # noqa: ARG002
                raise consul.exceptions.ACLPermissionDenied

        class DeniedConsul:
            def __init__(self, **kwargs):  # noqa: ARG002
                self.kv = DeniedKV()

        monkeypatch.setattr(consul.std, "Consul", DeniedConsul)
        src = ConsulSource(host="c", path="myapp")
        with pytest.raises(PermissionError, match="Consul auth failed"):
            src.load_raw()


@pytest.mark.usefixtures("_reset_config")
def test_missing_consul_raises_on_load(block_import, monkeypatch):
    """`import dature` works without consul; only _fetch() requires it."""
    monkeypatch.setenv("DATURE_CONSUL__HOST", "c")

    @dataclass
    class Config:
        foo: str = ""

    with block_import("consul"), pytest.raises(DatureConfigError) as exc_info:
        load(ConsulSource(path="p"), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == "'consul' is not installed. Run: pip install 'dature[consul]'"
