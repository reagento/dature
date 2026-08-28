"""Unit tests for gcp_secret_manager_ module (GcpSecretManagerSource).

Container-based integration tests live in ``tests/integration/sources/gcp_secret_manager/``.
"""

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from google.api_core.exceptions import NotFound, PermissionDenied, ServiceUnavailable, Unauthenticated
from google.auth.exceptions import DefaultCredentialsError

from dature import GcpSecretManagerSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group
from dature.loading.source_validation import validate_source
from dature.sources.base import remote_value_loaders, string_value_loaders
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestGcpSecretManagerSourceDisplayProperties:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("format_name", "gcp-secret-manager", id="format_name"),
            pytest.param("location_label", "GCP_SECRET_MANAGER", id="location_label"),
            pytest.param("config_group", "gcp_secret_manager", id="config_group"),
        ],
    )
    def test_class_attribute(self, attr, expected):
        assert getattr(GcpSecretManagerSource, attr) == expected

    @pytest.mark.parametrize(
        ("decode", "expected"),
        [
            pytest.param("utf-8", string_value_loaders(), id="utf8"),
            pytest.param("json", remote_value_loaders(), id="json"),
        ],
    )
    def test_format_loaders(self, decode, expected):
        src = GcpSecretManagerSource(project_id="my-proj", decode=decode)

        assert src.format_loaders() == expected

    def test_format_loaders_raises_on_unknown_decode(self):
        src = GcpSecretManagerSource(project_id="my-proj", decode="xml")

        with pytest.raises(ValueError, match="Unknown decode mode: 'xml'"):
            src.format_loaders()

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            pytest.param(
                {"project_id": "my-proj"},
                "gcp-secret-manager://my-proj/*/versions/latest",
                id="list_mode",
            ),
            pytest.param(
                {"project_id": "my-proj", "name": "app-config"},
                "gcp-secret-manager://my-proj/app-config/versions/latest",
                id="single_secret_mode",
            ),
            pytest.param(
                {"project_id": "my-proj", "name": "app-config", "version": "3"},
                "gcp-secret-manager://my-proj/app-config/versions/3",
                id="explicit_version",
            ),
        ],
    )
    def test_remote_address(self, kwargs, expected):
        src = GcpSecretManagerSource(**kwargs)

        assert src.remote_address() == expected


class TestGcpSecretManagerSourceBuildFilter:
    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            pytest.param({}, "", id="no_filter"),
            pytest.param({"name_prefix": "db-"}, "name:db-", id="prefix_only"),
            pytest.param({"labels": {"env": "prod"}}, "labels.env=prod", id="single_label"),
            pytest.param(
                {"labels": {"env": "prod", "team": "core"}},
                "labels.env=prod AND labels.team=core",
                id="multiple_labels_sorted",
            ),
            pytest.param(
                {"name_prefix": "db-", "labels": {"env": "prod"}},
                "name:db- AND labels.env=prod",
                id="prefix_and_labels",
            ),
        ],
    )
    def test_build_filter(self, kwargs, expected):
        src = GcpSecretManagerSource(project_id="my-proj", **kwargs)

        assert src._build_filter() == expected


@pytest.mark.usefixtures("_reset_config")
class TestGcpSecretManagerSourceValidation:
    def test_validate_raises_when_project_id_missing(self):
        merged = apply_source_config_group(GcpSecretManagerSource())

        with pytest.raises(ValueError, match="project_id is required"):
            validate_source(merged)

    def test_validate_passes_with_project_id(self):
        merged = apply_source_config_group(GcpSecretManagerSource(project_id="my-proj"))

        validate_source(merged)

    def test_validate_raises_on_credentials_and_credentials_file(self):
        merged = apply_source_config_group(
            GcpSecretManagerSource(project_id="my-proj", credentials=object(), credentials_file="key.json")
        )

        with pytest.raises(ValueError, match="mutually exclusive"):
            validate_source(merged)

    def test_validate_raises_on_transport_with_credentials(self):
        merged = apply_source_config_group(
            GcpSecretManagerSource(project_id="my-proj", transport=object(), credentials=object())
        )

        with pytest.raises(ValueError, match="transport cannot be combined"):
            validate_source(merged)

    def test_validate_raises_on_name_prefix_outside_list_mode(self):
        merged = apply_source_config_group(
            GcpSecretManagerSource(project_id="my-proj", name="app-config", name_prefix="db-")
        )

        with pytest.raises(ValueError, match="only apply in list mode"):
            validate_source(merged)

    def test_validate_raises_on_labels_outside_list_mode(self):
        merged = apply_source_config_group(
            GcpSecretManagerSource(project_id="my-proj", name="app-config", labels={"env": "prod"})
        )

        with pytest.raises(ValueError, match="only apply in list mode"):
            validate_source(merged)


@pytest.mark.usefixtures("_reset_config")
class TestGcpSecretManagerSourceConfigFallback:
    def test_project_id_from_configure(self):
        configure(gcp_secret_manager={"project_id": "from-configure"})

        merged = apply_source_config_group(GcpSecretManagerSource())

        assert merged.project_id == "from-configure"

    def test_project_id_from_env_var(self, monkeypatch):
        monkeypatch.setenv("DATURE_GCP_SECRET_MANAGER__PROJECT_ID", "from-env")

        merged = apply_source_config_group(GcpSecretManagerSource())

        assert merged.project_id == "from-env"

    def test_instance_overrides_global(self):
        configure(gcp_secret_manager={"project_id": "global-proj"})

        merged = apply_source_config_group(GcpSecretManagerSource(project_id="instance-proj"))

        assert merged.project_id == "instance-proj"


class FakeSecret:
    def __init__(self, name: str) -> None:
        self.name = name


class FakePayload:
    def __init__(self, data: bytes) -> None:
        self.data = data


class FakeAccessResponse:
    def __init__(self, payload: FakePayload) -> None:
        self.payload = payload


class FakeSecretManagerClient:
    def __init__(
        self,
        *,
        secret_ids: "list[str] | None" = None,
        values: "dict[str, str] | None" = None,
        list_error: Exception | None = None,
        get_error: Exception | None = None,
    ) -> None:
        self._secret_ids = secret_ids if secret_ids is not None else []
        self._values = values if values is not None else {}
        self._list_error = list_error
        self._get_error = get_error
        self.init_kwargs: dict[str, object] = {}
        self.get_secret_calls: list[tuple[str, str]] = []
        self.list_requests: list[dict[str, object]] = []

    def list_secrets(self, request: dict[str, object]) -> "list[FakeSecret]":
        self.list_requests.append(request)
        if self._list_error is not None:
            raise self._list_error
        parent = request["parent"]
        return [FakeSecret(f"{parent}/secrets/{secret_id}") for secret_id in self._secret_ids]

    def access_secret_version(self, name: str) -> FakeAccessResponse:
        secret_id = name.split("/secrets/")[1].split("/versions/", maxsplit=1)[0]
        version = name.rsplit("/versions/", 1)[-1]
        self.get_secret_calls.append((secret_id, version))
        if self._get_error is not None:
            raise self._get_error
        return FakeAccessResponse(FakePayload(self._values[secret_id].encode("utf-8")))


def _fake_client_factory(client: FakeSecretManagerClient) -> "Callable[..., FakeSecretManagerClient]":
    def _factory(*args: object, **kwargs: object) -> FakeSecretManagerClient:  # noqa: ARG001
        client.init_kwargs = kwargs
        return client

    return _factory


@dataclass
class _FetchConfig:
    foo: str = ""


class TestGcpSecretManagerSourceFetch:
    def _make_source(
        self, monkeypatch: pytest.MonkeyPatch, client: FakeSecretManagerClient, **kwargs: object
    ) -> GcpSecretManagerSource:
        monkeypatch.setattr("google.cloud.secretmanager.SecretManagerServiceClient", _fake_client_factory(client))
        kwargs.setdefault("project_id", "my-proj")
        kwargs.setdefault("credentials", object())
        kwargs.setdefault("expand_env_vars", "default")
        return GcpSecretManagerSource(**kwargs)

    def test_single_secret_mode(self, monkeypatch):
        client = FakeSecretManagerClient(values={"app-config": '{"host": "localhost"}'})
        src = self._make_source(monkeypatch, client, name="app-config", decode="json")

        result = src.load_raw()

        assert result.loaded_data == {"host": "localhost"}

    def test_single_secret_mode_passes_version(self, monkeypatch):
        client = FakeSecretManagerClient(values={"app-config": "v"})
        src = self._make_source(monkeypatch, client, name="app-config", version="3")

        src.load_raw()

        assert client.get_secret_calls == [("app-config", "3")]

    def test_list_mode_nests_on_separator(self, monkeypatch):
        client = FakeSecretManagerClient(
            secret_ids=["db--host", "db--port", "name"],
            values={"db--host": "localhost", "db--port": "5432", "name": "svc"},
        )
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"db": {"host": "localhost", "port": "5432"}, "name": "svc"}

    def test_list_mode_passes_filter(self, monkeypatch):
        client = FakeSecretManagerClient(secret_ids=["db-host"], values={"db-host": "localhost"})
        src = self._make_source(monkeypatch, client, name_prefix="db-")

        src.load_raw()

        assert client.list_requests == [{"parent": "projects/my-proj", "filter": "name:db-"}]

    def test_client_options_forwarded(self, monkeypatch):
        client = FakeSecretManagerClient(values={"app-config": "v"})
        src = self._make_source(
            monkeypatch, client, name="app-config", client_options={"api_endpoint": "localhost:9090"}
        )

        src.load_raw()

        assert client.init_kwargs["api_endpoint"] == "localhost:9090"

    def test_empty_project_raises_key_error(self, monkeypatch):
        client = FakeSecretManagerClient(secret_ids=[])
        src = self._make_source(monkeypatch, client)

        with pytest.raises(KeyError, match="GCP Secret Manager has no secrets"):
            src.load_raw()

    def test_not_found_raises_key_error(self, monkeypatch):
        client = FakeSecretManagerClient(get_error=NotFound("nope"))  # type: ignore[no-untyped-call]
        src = self._make_source(monkeypatch, client, name="missing")

        with pytest.raises(KeyError, match="GCP Secret Manager secret not found"):
            src.load_raw()

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(PermissionDenied("nope"), id="permission_denied"),  # type: ignore[no-untyped-call]
            pytest.param(Unauthenticated("nope"), id="unauthenticated"),  # type: ignore[no-untyped-call]
            pytest.param(
                DefaultCredentialsError("nope"),  # type: ignore[no-untyped-call]
                id="default_credentials_error",
            ),
        ],
    )
    def test_auth_error_raises_permission_error(self, monkeypatch, error):
        client = FakeSecretManagerClient(list_error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(PermissionError, match="GCP Secret Manager auth failed"):
            src.load_raw()

    def test_other_error_propagates(self, monkeypatch):
        client = FakeSecretManagerClient(list_error=ServiceUnavailable("boom"))  # type: ignore[no-untyped-call]
        src = self._make_source(monkeypatch, client)

        with pytest.raises(ServiceUnavailable):
            src.load_raw()

    def test_comprehensive_type_conversion(self, monkeypatch, all_types_gcp_secret_manager_file: Path):
        """Test loading via GcpSecretManagerSource (decode='utf-8') with full type coercion."""
        secret_map = json.loads(all_types_gcp_secret_manager_file.read_text())
        client = FakeSecretManagerClient(secret_ids=list(secret_map), values=secret_map)
        src = self._make_source(monkeypatch, client)

        result = load(src, schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_missing_secret_error_message_includes_address(self, monkeypatch):
        client = FakeSecretManagerClient(secret_ids=[])
        self._make_source(monkeypatch, client)

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                GcpSecretManagerSource(project_id="my-proj", credentials=object()),
                schema=_FetchConfig,
            )

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "'GCP Secret Manager has no secrets: gcp-secret-manager://my-proj/*/versions/latest'"
        )


@pytest.mark.usefixtures("_reset_config")
def test_missing_google_cloud_secretmanager_raises_on_load(monkeypatch):
    """`import dature` works without google-cloud-secret-manager; only _fetch() requires it.

    ``sys.modules[name] = None`` is the reliable way to simulate a missing dependency for a
    dotted package name — unlike ``block_import`` (which patches ``builtins.__import__``), it
    also blocks ``importlib.import_module`` used by ``require_dep``, since Python's import
    system raises ``ImportError`` immediately whenever a ``sys.modules`` entry is ``None``.
    """
    monkeypatch.setenv("DATURE_GCP_SECRET_MANAGER__PROJECT_ID", "my-proj")
    monkeypatch.setitem(sys.modules, "google.cloud.secretmanager", None)

    @dataclass
    class Config:
        foo: str = ""

    with pytest.raises(DatureConfigError) as exc_info:
        load(GcpSecretManagerSource(), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == (
        "'google.cloud.secretmanager' is not installed. Run: pip install 'dature[gcp]'"
    )
