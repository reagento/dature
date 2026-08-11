"""Unit tests for vault_ module (VaultSource).

Container-based integration tests live in ``tests/integration/sources/test_vault_.py``.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import hvac
import hvac.exceptions
import pytest

from dature import VaultSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group
from dature.loading.source_validation import validate_source
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestVaultSourceDisplayProperties:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("format_name", "vault", id="format_name"),
            pytest.param("location_label", "VAULT", id="location_label"),
            pytest.param("config_group", "vault", id="config_group"),
        ],
    )
    def test_class_attribute(self, attr, expected):
        assert getattr(VaultSource, attr) == expected

    @pytest.mark.parametrize(
        ("kv_version", "mount_point", "expected"),
        [
            pytest.param(2, "secret", "https://v:8200/v1/secret/data/myapp/config", id="v2"),
            pytest.param(1, "secret", "https://v:8200/v1/secret/myapp/config", id="v1"),
            pytest.param(None, "secret", "https://v:8200/v1/secret/data/myapp/config", id="default_kv_to_v2"),
            pytest.param(2, "kv", "https://v:8200/v1/kv/data/myapp/config", id="custom_mount"),
        ],
    )
    def test_remote_address_from_host_port_scheme(self, kv_version, mount_point, expected):
        src = VaultSource(
            host="v",
            port=8200,
            scheme="https",
            token="x",
            path="myapp/config",
            kv_version=kv_version,
            mount_point=mount_point,
        )
        assert src.remote_address() == expected

    def test_remote_address_url_overrides_host_port_scheme(self):
        with pytest.warns(DeprecationWarning, match="host=/port=/scheme="):
            src = VaultSource(
                url="https://v",
                host="ignored",
                port=1,
                scheme="http",
                token="x",
                path="myapp/config",
                mount_point="secret",
            )

        assert src.remote_address() == "https://v/v1/secret/data/myapp/config"

    def test_remote_address_url_trailing_slash_stripped(self):
        with pytest.warns(DeprecationWarning, match="host=/port=/scheme="):
            src = VaultSource(url="https://v/", token="x", path="myapp/config", mount_point="secret")

        assert src.remote_address() == "https://v/v1/secret/data/myapp/config"


class TestVaultSourceUrlDeprecation:
    def test_url_emits_deprecation_warning(self):
        with pytest.warns(DeprecationWarning, match="host=/port=/scheme="):
            VaultSource(url="https://v", token="x", path="p")

    def test_no_url_emits_no_warning(self, recwarn):
        VaultSource(host="v", token="x", path="p")

        assert len(recwarn) == 0


@pytest.mark.usefixtures("_reset_config")
class TestVaultSourceValidation:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            pytest.param({"path": "p"}, "token or role_id", id="no_auth"),
            pytest.param(
                {"path": "p", "token": "t", "role_id": "r", "secret_id": "s"},
                "mutually exclusive",
                id="mixed_auth",
            ),
            pytest.param(
                {"path": "p", "role_id": "r"},
                "token or role_id",
                id="approle_missing_secret_id",
            ),
            pytest.param(
                {"path": "p", "secret_id": "s"},
                "token or role_id",
                id="approle_missing_role_id",
            ),
        ],
    )
    def test_validate_raises_when_invalid(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            validate_source(apply_source_config_group(VaultSource(**kwargs)))

    def test_no_host_raises(self):
        # VaultConfig defaults host to "localhost", so the fallback group always fills it in
        # — "host is required" is only reachable when validate_source() runs on a bare instance
        # that skipped the config-group merge (e.g. config_group=None).
        with pytest.raises(ValueError, match="host is required"):
            validate_source(VaultSource(path="p", token="t"))

    @pytest.mark.parametrize(
        ("env_vars", "instance_kwargs"),
        [
            pytest.param(
                {"DATURE_VAULT__HOST": "x", "DATURE_VAULT__TOKEN": "t"},
                {},
                id="full_creds_from_env",
            ),
            pytest.param(
                {"DATURE_VAULT__HOST": "x", "DATURE_VAULT__SECRET_ID": "s"},
                {"role_id": "r"},
                id="approle_split_between_instance_and_env",
            ),
        ],
    )
    def test_validate_passes(self, monkeypatch, env_vars, instance_kwargs):
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)
        merged = apply_source_config_group(VaultSource(path="p", **instance_kwargs))
        validate_source(merged)


@pytest.mark.usefixtures("_reset_config")
class TestVaultSourceConfigFallback:
    def test_host_from_configure(self):
        configure(vault={"host": "from-configure", "token": "t"})
        merged = apply_source_config_group(VaultSource(path="p"))
        assert merged.host == "from-configure"
        assert merged.token == "t"

    def test_creds_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DATURE_VAULT__HOST", "localhost")
        monkeypatch.setenv("DATURE_VAULT__TOKEN", "root")
        merged = apply_source_config_group(VaultSource(path="myapp/config"))
        assert merged.host == "localhost"
        assert merged.token == "root"

    def test_instance_overrides_global(self):
        configure(vault={"host": "global", "token": "global-token"})
        merged = apply_source_config_group(VaultSource(path="p", host="instance"))
        assert merged.host == "instance"
        assert merged.token == "global-token"

    @pytest.mark.parametrize(
        ("global_value", "instance_value", "expected"),
        [
            pytest.param(1, None, 1, id="kv_version_from_global"),
            pytest.param(1, 2, 2, id="kv_version_instance_wins"),
            pytest.param(2, None, 2, id="kv_version_default"),
        ],
    )
    def test_kv_version_fallback(self, global_value, instance_value, expected):
        configure(vault={"host": "v", "token": "t", "kv_version": global_value})
        merged = apply_source_config_group(VaultSource(path="p", kv_version=instance_value))
        assert merged.kv_version == expected

    @pytest.mark.parametrize(
        ("global_value", "instance_value", "expected"),
        [
            pytest.param("kv1", "", "kv1", id="mount_point_from_global"),
            pytest.param("kv1", "secret2", "secret2", id="mount_point_instance_wins"),
            pytest.param(None, "", "secret", id="mount_point_default"),
        ],
    )
    def test_mount_point_fallback(self, global_value, instance_value, expected):
        config_kwargs = {"host": "v", "token": "t"}
        if global_value is not None:
            config_kwargs["mount_point"] = global_value
        configure(vault=config_kwargs)
        merged = apply_source_config_group(VaultSource(path="p", mount_point=instance_value))
        assert merged.mount_point == expected


class FakeKvV2:
    """Stand-in for hvac's ``client.secrets.kv.v2``."""

    def __init__(self, data: object) -> None:
        self._data = data

    def read_secret_version(self, *, path: str, mount_point: str) -> dict[str, object]:  # noqa: ARG002
        if self._data is None:
            raise hvac.exceptions.InvalidPath
        return {"data": {"data": self._data}}


class FakeSecrets:
    def __init__(self, data: object) -> None:
        self.kv = type("FakeKv", (), {"v2": FakeKvV2(data)})()


class FakeClient:
    def __init__(self, data: object, **kwargs: object) -> None:  # noqa: ARG002
        self.secrets = FakeSecrets(data)
        self.token = None


@dataclass
class _FetchConfig:
    port: int


class TestVaultSourceFetch:
    def _make_source(self, monkeypatch: pytest.MonkeyPatch, data: object, **kwargs: object) -> VaultSource:
        def _fake_client(**kw: object) -> FakeClient:
            return FakeClient(data, **kw)

        monkeypatch.setattr(hvac, "Client", _fake_client)
        return VaultSource(host="v", port=8200, scheme="https", token="t", path="myapp", **kwargs)

    def test_missing_path_error_message_includes_path(self, monkeypatch):
        self._make_source(monkeypatch, None)

        with pytest.raises(DatureConfigError) as exc_info:
            load(VaultSource(host="v", port=8200, scheme="https", token="t", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == "'Vault path not found: https://v:8200/v1/secret/data/myapp'"

    def test_bad_type_error_message_includes_path_and_value(self, monkeypatch):
        self._make_source(monkeypatch, {"port": "not_a_number"})

        with pytest.raises(DatureConfigError) as exc_info:
            load(VaultSource(host="v", port=8200, scheme="https", token="t", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "  [port]  invalid literal for int() with base 10: '<REDACTED>'\n"
            "   ├── https://v:8200/v1/secret/data/myapp: port = <REDACTED>\n"
            "   │                                               ^^^^^^^^^^"
        )

    def test_comprehensive_type_conversion(self, monkeypatch, all_types_vault_file: Path):
        """Test loading Vault KV v2's native-JSON payload with full type coercion."""
        payload = json.loads(all_types_vault_file.read_text())
        src = self._make_source(monkeypatch, payload)

        result = load(src, schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config")
def test_missing_hvac_raises_on_load(block_import, monkeypatch):
    """`import dature` works without hvac; only _fetch() requires it."""
    monkeypatch.setenv("DATURE_VAULT__HOST", "x")
    monkeypatch.setenv("DATURE_VAULT__TOKEN", "t")

    @dataclass
    class Config:
        foo: str = ""

    with block_import("hvac"), pytest.raises(DatureConfigError) as exc_info:
        load(VaultSource(path="p"), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == "'hvac' is not installed. Run: pip install 'dature[vault]'"
