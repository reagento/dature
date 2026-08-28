"""Integration tests for GcpSecretManagerSource — require a live Secret Manager emulator
container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.

Most tests here run against the plain emulator container (IAM enforcement off), so there is
no auth-failure case to trigger — that part of the docstring used to (incorrectly) claim it
was impossible in general. It isn't: ``TestGcpSecretManagerSourceIamEnforcement`` below stands
up a second, companion ``gcp-iam-emulator`` container in ``IAM_MODE=strict`` and drives it
through a transport-level interceptor that injects (or omits) an ``x-emulator-principal``
header — ``GcpSecretManagerSource`` itself has no principal concept, Application Default
Credentials are its real production auth path, so the header is the only lever the test layer
has. The unit tests in ``tests/sources/test_gcp_secret_manager_.py`` still separately cover the
``PermissionError`` mapping for ``PermissionDenied``/``Unauthenticated``/
``DefaultCredentialsError``, including ``DefaultCredentialsError``, which no emulator can
produce.
"""

import json
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest
from google.cloud import secretmanager
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network

from dature import GcpSecretManagerSource, configure, load
from dature.errors import DatureConfigError
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.integration.sources.gcp_secret_manager.conftest import GCP_PROJECT_ID
from tests.integration.sources.gcp_secret_manager.helpers import (
    GCP_IAM_EMULATOR_HOST_PORT,
    GCP_SECRET_MANAGER_IAM_GRPC_PORT,
    GCP_SECRET_MANAGER_IAM_REST_PORT,
    IAM_NETWORK_ALIAS,
    TEST_PRINCIPAL,
    grant_secret_manager_admin,
    secret_manager_grpc_transport,
    start_iam_emulator,
    start_secret_manager_emulator,
)
from tests.sources.checker import assert_all_types_equal

EXPECTED_SECRET: Final = {"password": "s3cret", "port": "5432", "name": "myapp"}


@dataclass
class _Config:
    password: str
    port: int
    name: str


EXPECTED_DATACLASS: Final = _Config(password="s3cret", port=5432, name="myapp")


@pytest.fixture
def gcp_secret_manager_client(gcp_secret_manager_transport: object) -> secretmanager.SecretManagerServiceClient:
    return secretmanager.SecretManagerServiceClient(transport=gcp_secret_manager_transport)


def _create_secret(
    client: secretmanager.SecretManagerServiceClient,
    secret_id: str,
    value: str,
    *,
    labels: dict[str, str] | None = None,
) -> None:
    secret: dict[str, object] = {"replication": {"automatic": {}}}
    if labels:
        secret["labels"] = labels
    client.create_secret(parent=f"projects/{GCP_PROJECT_ID}", secret_id=secret_id, secret=secret)
    client.add_secret_version(
        parent=f"projects/{GCP_PROJECT_ID}/secrets/{secret_id}",
        payload={"data": value.encode("utf-8")},
    )


@pytest.fixture
def _secrets(gcp_secret_manager_client: secretmanager.SecretManagerServiceClient):
    for name, value in EXPECTED_SECRET.items():
        _create_secret(gcp_secret_manager_client, name, value)


@pytest.fixture
def _secrets_all_types(
    gcp_secret_manager_client: secretmanager.SecretManagerServiceClient,
    all_types_gcp_secret_manager_file: Path,
):
    secret_map = json.loads(all_types_gcp_secret_manager_file.read_text())
    for key, value in secret_map.items():
        _create_secret(gcp_secret_manager_client, key, value)


def _make_source(transport: object, **kwargs: object) -> GcpSecretManagerSource:
    return GcpSecretManagerSource(project_id=GCP_PROJECT_ID, transport=transport, **kwargs)


@pytest.mark.usefixtures("_reset_config")
class TestGcpSecretManagerSourceListMode:
    @pytest.mark.usefixtures("_secrets")
    def test_load_basic(self, gcp_secret_manager_transport: object):
        result = load(_make_source(gcp_secret_manager_transport), schema=_Config)

        assert result == EXPECTED_DATACLASS


@pytest.mark.usefixtures("_reset_config")
class TestGcpSecretManagerSourceSingleSecretMode:
    def test_load_json_document(
        self,
        gcp_secret_manager_client: secretmanager.SecretManagerServiceClient,
        gcp_secret_manager_transport: object,
    ):
        _create_secret(gcp_secret_manager_client, "app-config", json.dumps(EXPECTED_SECRET))

        result = load(
            _make_source(gcp_secret_manager_transport, name="app-config", decode="json"),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS


@pytest.mark.usefixtures("_reset_config")
class TestGcpSecretManagerSourceFiltering:
    def test_name_prefix_filters_list_mode(
        self,
        gcp_secret_manager_client: secretmanager.SecretManagerServiceClient,
        gcp_secret_manager_transport: object,
    ):
        _create_secret(gcp_secret_manager_client, "dbpassword", "s3cret")
        _create_secret(gcp_secret_manager_client, "other", "ignored")

        result: object = load(
            _make_source(gcp_secret_manager_transport, name_prefix="db"),
            schema=_make_dbpassword_only_schema(),
        )

        assert result.dbpassword == "s3cret"

    def test_labels_filter_list_mode(
        self,
        gcp_secret_manager_client: secretmanager.SecretManagerServiceClient,
        gcp_secret_manager_transport: object,
    ):
        _create_secret(gcp_secret_manager_client, "password", "yes", labels={"env": "prod"})
        _create_secret(gcp_secret_manager_client, "otherfield", "no", labels={"env": "dev"})

        result: object = load(
            _make_source(gcp_secret_manager_transport, labels={"env": "prod"}),
            schema=_make_password_only_schema(),
        )

        assert result.password == "yes"


def _make_password_only_schema() -> type:
    @dataclass
    class _PasswordOnly:
        password: str = ""

    return _PasswordOnly


def _make_dbpassword_only_schema() -> type:
    @dataclass
    class _DbPasswordOnly:
        dbpassword: str = ""

    return _DbPasswordOnly


@pytest.mark.usefixtures("_reset_config")
class TestGcpSecretManagerSourceAllTypes:
    @pytest.mark.usefixtures("_secrets_all_types")
    def test_comprehensive_type_conversion(self, gcp_secret_manager_transport: object):
        result = load(_make_source(gcp_secret_manager_transport), schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config", "_secrets")
class TestGcpSecretManagerSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="project_id_from_configure"),
            pytest.param("env", id="project_id_from_env"),
        ],
    )
    def test_load_with_settings(
        self,
        via: str,
        gcp_secret_manager_transport: object,
        monkeypatch: pytest.MonkeyPatch,
    ):
        if via == "configure":
            configure(gcp_secret_manager={"project_id": GCP_PROJECT_ID})
        else:
            monkeypatch.setenv("DATURE_GCP_SECRET_MANAGER__PROJECT_ID", GCP_PROJECT_ID)

        result = load(
            GcpSecretManagerSource(transport=gcp_secret_manager_transport),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS


@pytest.fixture(scope="class")
def _iam_network() -> Generator[Network]:
    with Network() as network:
        yield network


@pytest.fixture(scope="class")
def _iam_emulator(_iam_network: Network) -> Generator[DockerContainer]:
    yield from start_iam_emulator(_iam_network, GCP_IAM_EMULATOR_HOST_PORT)


@pytest.fixture(scope="class")
def _iam_enforced_secret_manager(_iam_network: Network, _iam_emulator: DockerContainer) -> Generator[DockerContainer]:
    yield from start_secret_manager_emulator(
        GCP_SECRET_MANAGER_IAM_GRPC_PORT,
        GCP_SECRET_MANAGER_IAM_REST_PORT,
        network=_iam_network,
        iam_host=f"{IAM_NETWORK_ALIAS}:{GCP_IAM_EMULATOR_HOST_PORT}",
    )


@pytest.fixture(scope="class")
def gcp_secret_manager_iam_transport(_iam_enforced_secret_manager: DockerContainer) -> "object":
    """Plain transport (no principal) against the IAM-enforced emulator."""
    return secret_manager_grpc_transport(GCP_SECRET_MANAGER_IAM_GRPC_PORT)


@pytest.fixture(scope="class")
def gcp_secret_manager_admin_transport(_iam_enforced_secret_manager: DockerContainer) -> "object":
    """Transport injecting ``TEST_PRINCIPAL``, which holds ``roles/secretmanager.admin``."""
    grant_secret_manager_admin(GCP_IAM_EMULATOR_HOST_PORT, GCP_PROJECT_ID, TEST_PRINCIPAL)
    return secret_manager_grpc_transport(GCP_SECRET_MANAGER_IAM_GRPC_PORT, principal=TEST_PRINCIPAL)


@pytest.mark.usefixtures("_reset_config")
class TestGcpSecretManagerSourceIamEnforcement:
    """Drives the two-container IAM-enforced stack to trigger a genuine, emulator-originated
    auth failure — see the module docstring for why the principal is injected at the
    transport layer rather than through ``GcpSecretManagerSource`` itself."""

    @pytest.fixture(autouse=True)
    def _seed_secrets(self, gcp_secret_manager_admin_transport: object):
        client = secretmanager.SecretManagerServiceClient(transport=gcp_secret_manager_admin_transport)
        for name, value in EXPECTED_SECRET.items():
            _create_secret(client, name, value)

    def test_authorized_principal_loads(self, gcp_secret_manager_admin_transport: object):
        result = load(_make_source(gcp_secret_manager_admin_transport), schema=_Config)

        assert result == EXPECTED_DATACLASS

    @pytest.mark.parametrize(
        "name",
        [
            pytest.param("*", id="list_mode"),
            pytest.param("app-config", id="single_secret_mode"),
        ],
    )
    def test_no_principal_raises_permission_error(self, name: str, gcp_secret_manager_iam_transport: object):
        with pytest.raises(DatureConfigError) as exc_info:
            load(_make_source(gcp_secret_manager_iam_transport, name=name), schema=_Config)

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, PermissionError)
        assert inner.args[0] == (
            f"GCP Secret Manager auth failed for gcp-secret-manager://{GCP_PROJECT_ID}/{name}/versions/latest"
        )
