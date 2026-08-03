"""Unit tests for vault_ module (VaultSource).

Container-based integration tests live in ``tests/integration/sources/test_vault_.py``.
"""

from dataclasses import dataclass

import hvac
import hvac.exceptions
import pytest

from dature import VaultSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group


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
            pytest.param(2, "secret", "https://v/v1/secret/data/myapp/config", id="v2"),
            pytest.param(1, "secret", "https://v/v1/secret/myapp/config", id="v1"),
            pytest.param(None, "secret", "https://v/v1/secret/data/myapp/config", id="default_kv_to_v2"),
            pytest.param(2, "kv", "https://v/v1/kv/data/myapp/config", id="custom_mount"),
        ],
    )
    def test_remote_address(self, kv_version, mount_point, expected):
        src = VaultSource(
            url="https://v",
            token="x",
            path="myapp/config",
            kv_version=kv_version,
            mount_point=mount_point,
        )
        assert src.remote_address() == expected


@pytest.mark.usefixtures("_reset_config")
class TestVaultSourceValidation:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            pytest.param({"path": "p"}, "url is required", id="no_url"),
            pytest.param({"path": "p", "url": "u"}, "token or role_id", id="no_auth"),
            pytest.param(
                {"path": "p", "url": "u", "token": "t", "role_id": "r", "secret_id": "s"},
                "mutually exclusive",
                id="mixed_auth",
            ),
            pytest.param(
                {"path": "p", "url": "u", "role_id": "r"},
                "token or role_id",
                id="approle_missing_secret_id",
            ),
            pytest.param(
                {"path": "p", "url": "u", "secret_id": "s"},
                "token or role_id",
                id="approle_missing_role_id",
            ),
        ],
    )
    def test_validate_raises_when_invalid(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            apply_source_config_group(VaultSource(**kwargs)).check_invariants()

    @pytest.mark.parametrize(
        ("env_vars", "instance_kwargs"),
        [
            pytest.param(
                {"DATURE_VAULT__URL": "http://x", "DATURE_VAULT__TOKEN": "t"},
                {},
                id="full_creds_from_env",
            ),
            pytest.param(
                {"DATURE_VAULT__URL": "http://x", "DATURE_VAULT__SECRET_ID": "s"},
                {"role_id": "r"},
                id="approle_split_between_instance_and_env",
            ),
        ],
    )
    def test_validate_passes(self, monkeypatch, env_vars, instance_kwargs):
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)
        merged = apply_source_config_group(VaultSource(path="p", **instance_kwargs))
        merged.check_invariants()


@pytest.mark.usefixtures("_reset_config")
class TestVaultSourceConfigFallback:
    def test_url_from_configure(self):
        configure(vault={"url": "http://from-configure", "token": "t"})
        merged = apply_source_config_group(VaultSource(path="p"))
        assert merged.url == "http://from-configure"
        assert merged.token == "t"

    def test_creds_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DATURE_VAULT__URL", "http://localhost:8200")
        monkeypatch.setenv("DATURE_VAULT__TOKEN", "root")
        merged = apply_source_config_group(VaultSource(path="myapp/config"))
        assert merged.url == "http://localhost:8200"
        assert merged.token == "root"

    def test_instance_overrides_global(self):
        configure(vault={"url": "http://global", "token": "global-token"})
        merged = apply_source_config_group(VaultSource(path="p", url="http://instance"))
        assert merged.url == "http://instance"
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
        configure(vault={"url": "u", "token": "t", "kv_version": global_value})
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
        config_kwargs = {"url": "u", "token": "t"}
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
        return VaultSource(url="https://v", token="t", path="myapp", **kwargs)

    def test_missing_path_error_message_includes_path(self, monkeypatch):
        self._make_source(monkeypatch, None)

        with pytest.raises(DatureConfigError) as exc_info:
            load(VaultSource(url="https://v", token="t", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == "'Vault path not found: https://v/v1/secret/data/myapp'"

    def test_bad_type_error_message_includes_path_and_value(self, monkeypatch):
        self._make_source(monkeypatch, {"port": "not_a_number"})

        with pytest.raises(DatureConfigError) as exc_info:
            load(VaultSource(url="https://v", token="t", path="myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "  [port]  invalid literal for int() with base 10: 'not_a_number'\n"
            "   ├── https://v/v1/secret/data/myapp: port = not_a_number"
        )


@pytest.mark.usefixtures("_reset_config")
def test_missing_hvac_raises_on_load(block_import, monkeypatch):
    """`import dature` works without hvac; only _fetch() requires it."""
    monkeypatch.setenv("DATURE_VAULT__URL", "http://x")
    monkeypatch.setenv("DATURE_VAULT__TOKEN", "t")

    @dataclass
    class Config:
        foo: str = ""

    with block_import("hvac"), pytest.raises(DatureConfigError) as exc_info:
        load(VaultSource(path="p"), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == "'hvac' is not installed. Run: pip install 'dature[vault]'"
