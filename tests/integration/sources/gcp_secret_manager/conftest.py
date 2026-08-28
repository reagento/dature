"""Shared fixtures for GcpSecretManagerSource integration tests under
``tests/integration/sources/gcp_secret_manager/``.

Uses ``ghcr.io/blackwell-systems/gcp-secret-manager-emulator-dual`` (a third-party Secret
Manager test double — there is no official Google emulator, unlike Firestore/Datastore/
Pub-Sub). It requires no credentials and speaks plaintext gRPC, reached via a pre-built
``SecretManagerServiceGrpcTransport`` over ``grpc.insecure_channel``.

This emulator's server-side filter parser (``parseSecretFilter``) only supports a single
filter expression at a time (``name:<prefix>`` OR ``labels.<k>=<v>``) and treats anything
else as "match all" — unlike real GCP, which supports ``AND``-composed filters. Integration
tests below therefore exercise ``name_prefix`` and ``labels`` filtering separately; the
combined ``name_prefix`` + ``labels`` case (an ``AND`` of both) is only covered by the exact
filter-string assertions in ``tests/sources/test_gcp_secret_manager_.py``.

The container started here has IAM enforcement off (the emulator's default), which is why
``gcp_secret_manager_transport`` needs no credentials at all. For a real, enforced
auth-failure case — a companion ``gcp-iam-emulator`` container in ``IAM_MODE=strict`` — see
``TestGcpSecretManagerSourceIamEnforcement`` in ``test_gcp_secret_manager_.py``. The container
here is bound to fixed host ports (rather than testcontainers' usual random ports) since both
the gRPC and REST endpoints are fixed by the image.
"""

from collections.abc import Generator

import pytest
from testcontainers.core.container import DockerContainer

from tests.integration.sources.gcp_secret_manager.helpers import (
    GCP_SECRET_MANAGER_EMULATOR_GRPC_PORT,
    GCP_SECRET_MANAGER_EMULATOR_REST_PORT,
    secret_manager_grpc_transport,
    start_secret_manager_emulator,
)

GCP_PROJECT_ID = "test-project"


@pytest.fixture
def gcp_secret_manager_container() -> Generator[DockerContainer]:
    """A fresh emulator container per test, bound to fixed host ports.

    GcpSecretManagerSource's list mode (``name="*"``) enumerates every secret matching the
    filter in the project — a container shared across tests would leak secrets from one
    test into another's "list all" assertions. A dedicated container per test trades
    startup cost for correctness here.
    """
    yield from start_secret_manager_emulator(
        GCP_SECRET_MANAGER_EMULATOR_GRPC_PORT, GCP_SECRET_MANAGER_EMULATOR_REST_PORT
    )


@pytest.fixture
def gcp_secret_manager_transport(gcp_secret_manager_container: DockerContainer) -> "object":  # noqa: ARG001
    """A gRPC transport pointed at the emulator, blocked until it accepts connections."""
    return secret_manager_grpc_transport(GCP_SECRET_MANAGER_EMULATOR_GRPC_PORT)
