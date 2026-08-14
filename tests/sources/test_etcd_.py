"""Unit tests for etcd_ module (EtcdSource).

Container-based integration tests live in ``tests/integration/sources/etcd/``.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import etcd3gw.client
import etcd3gw.exceptions
import pytest

from dature import EtcdSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group
from dature.loading.source_validation import validate_source
from dature.sources.base import bytes_value_loaders, remote_value_loaders, string_value_loaders
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestEtcdSourceDisplayProperties:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("format_name", "etcd", id="format_name"),
            pytest.param("location_label", "ETCD", id="location_label"),
            pytest.param("config_group", "etcd", id="config_group"),
        ],
    )
    def test_class_attribute(self, attr, expected):
        assert getattr(EtcdSource, attr) == expected

    @pytest.mark.parametrize(
        ("decode", "expected"),
        [
            pytest.param("utf-8", string_value_loaders(), id="utf8"),
            pytest.param("json", remote_value_loaders(), id="json"),
            pytest.param("raw", bytes_value_loaders(), id="raw"),
        ],
    )
    def test_format_loaders(self, decode, expected):
        src = EtcdSource(host="e", path="myapp", decode=decode)

        loaders = src.format_loaders()

        assert loaders == expected

    def test_format_loaders_raises_on_unknown_decode(self):
        src = EtcdSource(host="e", path="myapp", decode="xml")

        with pytest.raises(ValueError, match="Unknown decode mode: 'xml'"):
            src.format_loaders()

    def test_decode_value_raises_on_unknown_decode(self):
        src = EtcdSource(host="e", path="myapp", decode="xml")

        with pytest.raises(ValueError, match="Unknown decode mode: 'xml'"):
            src._decode_value(b"data")

    @pytest.mark.usefixtures("_reset_config")
    @pytest.mark.parametrize(
        ("protocol", "host", "port", "path", "expected"),
        [
            pytest.param("https", "e", 2379, "myapp/config", "https://e:2379/v3/kv/myapp/config", id="explicit"),
            pytest.param(
                None, "e", None, "myapp/config", "http://e:2379/v3/kv/myapp/config", id="default_protocol_port"
            ),
            pytest.param("http", "", None, "p", "http://localhost:2379/v3/kv/p", id="default_host"),
        ],
    )
    def test_remote_address(self, protocol, host, port, path, expected):
        src = apply_source_config_group(EtcdSource(host=host, port=port, protocol=protocol, path=path))

        address = src.remote_address()

        assert address == expected


@pytest.mark.usefixtures("_reset_config")
class TestEtcdSourceValidation:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            pytest.param({"path": "p", "host": "e", "protocol": "ftp"}, "protocol must be", id="bad_protocol"),
            pytest.param({"path": "p", "host": "e", "decode": "xml"}, "decode must be", id="bad_decode"),
            pytest.param({"path": "p", "host": "e", "port": 0}, "port must be", id="zero_port"),
            pytest.param({"path": "p", "host": "e", "port": -1}, "port must be", id="negative_port"),
            pytest.param({"path": "p", "host": "e", "user": "u"}, "must be set together", id="user_without_password"),
            pytest.param(
                {"path": "p", "host": "e", "password": "pw"}, "must be set together", id="password_without_user"
            ),
        ],
    )
    def test_validate_raises_when_invalid(self, kwargs, match):
        merged = apply_source_config_group(EtcdSource(**kwargs))

        with pytest.raises(ValueError, match=match):
            validate_source(merged)

    def test_no_host_raises(self):
        # EtcdConfig defaults host to "localhost", so the fallback group always fills it in
        # — "host is required" is only reachable when validate_source() runs on a bare instance
        # that skipped the config-group merge (e.g. config_group=None).
        src = EtcdSource(path="p")

        with pytest.raises(ValueError, match="host is required"):
            validate_source(src)

    def test_validate_passes(self):
        merged = apply_source_config_group(EtcdSource(path="p", host="e"))

        validate_source(merged)

    def test_validate_passes_with_user_and_password(self):
        merged = apply_source_config_group(EtcdSource(path="p", host="e", user="u", password="pw"))

        validate_source(merged)


@pytest.mark.usefixtures("_reset_config")
class TestEtcdSourceConfigFallback:
    def test_host_from_configure(self):
        configure(etcd={"host": "from-configure", "user": "u", "password": "pw"})

        merged = apply_source_config_group(EtcdSource(path="p"))

        assert merged.host == "from-configure"
        assert merged.user == "u"
        assert merged.password == "pw"

    def test_creds_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DATURE_ETCD__HOST", "localhost")
        monkeypatch.setenv("DATURE_ETCD__USER", "root")
        monkeypatch.setenv("DATURE_ETCD__PASSWORD", "root-pw")

        merged = apply_source_config_group(EtcdSource(path="myapp/config"))

        assert merged.host == "localhost"
        assert merged.user == "root"
        assert merged.password == "root-pw"

    def test_instance_overrides_global(self):
        configure(etcd={"host": "global", "user": "global-user", "password": "global-pw"})

        merged = apply_source_config_group(EtcdSource(path="p", host="instance"))

        assert merged.host == "instance"
        assert merged.user == "global-user"

    @pytest.mark.parametrize(
        ("global_value", "instance_value", "expected"),
        [
            pytest.param(2379, None, 2379, id="port_from_global"),
            pytest.param(2379, 2380, 2380, id="port_instance_wins"),
            pytest.param(None, None, 2379, id="port_default"),
        ],
    )
    def test_port_fallback(self, global_value, instance_value, expected):
        config_kwargs = {"host": "e"}
        if global_value is not None:
            config_kwargs["port"] = global_value
        configure(etcd=config_kwargs)

        merged = apply_source_config_group(EtcdSource(path="p", port=instance_value))

        assert merged.port == expected

    @pytest.mark.parametrize(
        ("global_value", "instance_value", "expected"),
        [
            pytest.param("https", None, "https", id="protocol_from_global"),
            pytest.param("https", "http", "http", id="protocol_instance_wins"),
            pytest.param(None, None, "http", id="protocol_default"),
        ],
    )
    def test_protocol_fallback(self, global_value, instance_value, expected):
        config_kwargs = {"host": "e"}
        if global_value is not None:
            config_kwargs["protocol"] = global_value
        configure(etcd=config_kwargs)

        merged = apply_source_config_group(EtcdSource(path="p", protocol=instance_value))

        assert merged.protocol == expected


class FakeEtcd3Client:
    """Stand-in for ``etcd3gw.client.Etcd3Client``."""

    def __init__(self, get_prefix_data: object = None, get_data: object = None, **kwargs: object) -> None:  # noqa: ARG002
        self._get_prefix_data = get_prefix_data if get_prefix_data is not None else []
        self._get_data = get_data if get_data is not None else []

    def get_prefix(self, path: str) -> object:  # noqa: ARG002
        return self._get_prefix_data

    def get(self, path: str) -> object:  # noqa: ARG002
        return self._get_data


@dataclass
class _FetchConfig:
    port: int


class TestEtcdSourceFetch:
    def _make_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        get_prefix_data: object = None,
        get_data: object = None,
        **kwargs: object,
    ) -> EtcdSource:
        def _fake_client(**kw: object) -> FakeEtcd3Client:
            return FakeEtcd3Client(get_prefix_data=get_prefix_data, get_data=get_data, **kw)

        monkeypatch.setattr(sys.modules["etcd3gw.client"], "Etcd3Client", _fake_client)
        kwargs.setdefault("path", "myapp")
        kwargs.setdefault("expand_env_vars", "default")
        return EtcdSource(host="e", **kwargs)

    def test_recursive_nests_on_separator(self, monkeypatch):
        data = [
            (b"localhost", {"key": b"myapp/db/host"}),
            (b"5432", {"key": b"myapp/db/port"}),
            (b"svc", {"key": b"myapp/name"}),
        ]
        src = self._make_source(monkeypatch, get_prefix_data=data)

        result = src.load_raw()

        assert result.loaded_data == {
            "db": {"host": "localhost", "port": 5432},
            "name": "svc",
        }

    def test_recursive_drops_exact_prefix_key(self, monkeypatch):
        # A key that equals the prefix itself has no leaf name and is dropped.
        data = [
            (b"", {"key": b"myapp"}),
            (b"svc", {"key": b"myapp/name"}),
        ]
        src = self._make_source(monkeypatch, get_prefix_data=data)

        result = src.load_raw()

        assert result.loaded_data == {"name": "svc"}

    def test_recursive_separator_none_keeps_flat_keys(self, monkeypatch):
        data = [
            (b"localhost", {"key": b"myapp/db/host"}),
            (b"svc", {"key": b"myapp/name"}),
        ]
        src = self._make_source(monkeypatch, get_prefix_data=data, separator=None)

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
        data = [(raw_value, {"key": b"myapp/host"})]
        src = self._make_source(monkeypatch, get_prefix_data=data, decode=decode)

        result = src.load_raw()

        assert result.loaded_data == {"host": expected}

    def test_single_key_json_becomes_root(self, monkeypatch):
        src = self._make_source(
            monkeypatch, get_data=[b'{"db": {"host": "localhost"}}'], recursive=False, decode="json"
        )

        result = src.load_raw()

        assert result.loaded_data == {"db": {"host": "localhost"}}

    def test_single_key_non_json_uses_last_segment(self, monkeypatch):
        src = self._make_source(monkeypatch, get_data=[b"svc"], path="myapp/name", recursive=False)

        result = src.load_raw()

        assert result.loaded_data == {"name": "svc"}

    def test_missing_prefix_raises_key_error(self, monkeypatch):
        src = self._make_source(monkeypatch, get_prefix_data=[])

        with pytest.raises(KeyError, match="etcd key not found"):
            src.load_raw()

    def test_missing_single_key_raises_key_error(self, monkeypatch):
        src = self._make_source(monkeypatch, get_data=[], recursive=False)

        with pytest.raises(KeyError, match="etcd key not found"):
            src.load_raw()

    def test_comprehensive_type_conversion(self, monkeypatch, all_types_etcd_kv_file: Path):
        """Test loading a recursive etcd prefix tree (decode='utf-8') with full type coercion."""
        kv_map = json.loads(all_types_etcd_kv_file.read_text())
        data = [
            (value.encode("utf-8"), {"key": key.replace("all_types", "myapp", 1).encode("utf-8")})
            for key, value in kv_map.items()
        ]
        src = self._make_source(monkeypatch, get_prefix_data=data)

        result = load(src, schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_missing_key_error_message_includes_path(self, monkeypatch):
        self._make_source(monkeypatch, get_prefix_data=[])

        with pytest.raises(DatureConfigError) as exc_info:
            load(EtcdSource(host="e", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == "'etcd key not found: http://e:2379/v3/kv/myapp'"

    def test_bad_type_error_message_includes_path_and_value(self, monkeypatch):
        data = [(b"not_a_number", {"key": b"myapp/port"})]
        self._make_source(monkeypatch, get_prefix_data=data)

        with pytest.raises(DatureConfigError) as exc_info:
            load(EtcdSource(host="e", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "  [port]  invalid literal for int() with base 10: '<REDACTED>'\n"
            "   ├── http://e:2379/v3/kv/myapp: port = <REDACTED>\n"
            "   │                                     ^^^^^^^^^^"
        )

    def test_raw_decode_loads_into_bytes_field(self, monkeypatch):
        data = [(b"\x00\x01raw", {"key": b"myapp/blob"})]
        self._make_source(monkeypatch, get_prefix_data=data, decode="raw")

        @dataclass
        class Config:
            blob: bytes

        result = load(EtcdSource(host="e", path="myapp", decode="raw"), schema=Config)

        assert result == Config(blob=b"\x00\x01raw")

    def test_auth_failure_raises_permission_error(self, monkeypatch):
        class DeniedClient:
            def __init__(self, **kwargs):
                pass

            def get_prefix(self, path):  # noqa: ARG002
                msg = "Forbidden"
                raise etcd3gw.exceptions.Etcd3Exception(msg, msg)

        monkeypatch.setattr(sys.modules["etcd3gw.client"], "Etcd3Client", DeniedClient)
        src = EtcdSource(host="e", path="myapp")

        with pytest.raises(PermissionError, match="etcd auth failed"):
            src.load_raw()

    def test_other_etcd_exception_propagates(self, monkeypatch):
        class BrokenClient:
            def __init__(self, **kwargs):
                pass

            def get_prefix(self, path):  # noqa: ARG002
                msg = "boom"
                raise etcd3gw.exceptions.InternalServerError(msg, msg)

        monkeypatch.setattr(sys.modules["etcd3gw.client"], "Etcd3Client", BrokenClient)
        src = EtcdSource(host="e", path="myapp")

        with pytest.raises(etcd3gw.exceptions.InternalServerError):
            src.load_raw()

    def test_wrong_password_during_fetch_raises_permission_error(self, monkeypatch):
        class RejectingClient:
            def __init__(self, **kwargs):
                pass

            def get_url(self, path):  # noqa: ARG002
                return "http://e:2379/v3/auth/authenticate"

            def post(self, url, json):  # noqa: ARG002
                msg = "Unauthorized"
                raise etcd3gw.exceptions.Etcd3Exception(msg, msg)

        monkeypatch.setattr(sys.modules["etcd3gw.client"], "Etcd3Client", RejectingClient)
        src = EtcdSource(host="e", path="myapp", user="root", password="wrong")

        with pytest.raises(PermissionError, match="etcd auth failed"):
            src.load_raw()


class _FakeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


class FakeAuthClient:
    """Stand-in for ``Etcd3Client`` exposing just what ``_authenticate`` touches."""

    def __init__(self, post_result: object) -> None:
        self._post_result = post_result
        self.posted_to: str | None = None
        self.posted_json: object = None
        self.session = _FakeSession()

    def get_url(self, path: str) -> str:
        return f"http://e:2379/v3{path}"

    def post(self, url: str, json: object) -> object:
        self.posted_to = url
        self.posted_json = json
        if isinstance(self._post_result, Exception):
            raise self._post_result
        return self._post_result


class TestEtcdSourceAuth:
    def test_no_user_skips_authenticate_call(self):
        src = EtcdSource(host="e", path="myapp")
        client = FakeAuthClient(post_result=AssertionError("should not be called"))

        src._authenticate(client)

        assert client.posted_to is None
        assert "Authorization" not in client.session.headers

    def test_user_authenticates_and_sets_token(self):
        src = EtcdSource(host="e", path="myapp", user="root", password="root-pw")
        client = FakeAuthClient(post_result={"token": "tok123"})

        src._authenticate(client)

        assert client.session.headers["Authorization"] == "tok123"
        assert client.posted_to == "http://e:2379/v3/auth/authenticate"
        assert client.posted_json == {"name": "root", "password": "root-pw"}

    def test_user_auth_failure_raises_permission_error(self):
        src = EtcdSource(host="e", path="myapp", user="root", password="wrong")
        client = FakeAuthClient(post_result={})

        with pytest.raises(PermissionError, match="etcd auth failed"):
            src._authenticate(client)


@pytest.mark.usefixtures("_reset_config")
def test_missing_etcd_raises_on_load(block_import, monkeypatch):
    """`import dature` works without etcd3gw; only _fetch() requires it."""
    monkeypatch.setenv("DATURE_ETCD__HOST", "e")

    @dataclass
    class Config:
        foo: str = ""

    with block_import("etcd3gw"), pytest.raises(DatureConfigError) as exc_info:
        load(EtcdSource(path="p"), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == "'etcd3gw' is not installed. Run: pip install 'dature[etcd]'"
