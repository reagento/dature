"""Shared, fixture-independent helpers for GcpSecretManagerSource integration tests.

Kept separate from ``conftest.py`` so both it and the test modules can import these
without going through pytest fixture injection. Covers both the plain data-plane emulator
(``gcp-secret-manager-emulator-dual``) and, for the IAM-enforcement tests, the companion
control-plane container (``gcp-iam-emulator``) plus the principal-injection interceptor and
policy-grant helper needed to drive it.
"""

from collections.abc import Generator
from typing import Any, Final

import grpc
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network

from tests.integration.waiting import retry_until_ready

GCP_SECRET_MANAGER_EMULATOR_IMAGE: Final = "ghcr.io/blackwell-systems/gcp-secret-manager-emulator-dual:1.9.0"
GCP_SECRET_MANAGER_EMULATOR_GRPC_PORT: Final = 9090
GCP_SECRET_MANAGER_EMULATOR_REST_PORT: Final = 8080

GCP_IAM_EMULATOR_IMAGE: Final = "ghcr.io/blackwell-systems/gcp-iam-emulator:v0.10.2"
GCP_IAM_EMULATOR_INTERNAL_PORT: Final = 8080
GCP_IAM_EMULATOR_HOST_PORT: Final = 8083
GCP_SECRET_MANAGER_IAM_GRPC_PORT: Final = 9092
GCP_SECRET_MANAGER_IAM_REST_PORT: Final = 8082
IAM_NETWORK_ALIAS: Final = "iam"
TEST_PRINCIPAL: Final = "serviceAccount:test-principal"


def start_secret_manager_emulator(
    grpc_port: int,
    rest_port: int,
    *,
    network: Network | None = None,
    iam_host: str | None = None,
) -> Generator[DockerContainer]:
    """Start one Secret Manager emulator container, bound to fixed host ports, and yield it.

    With *network* and *iam_host* left at their defaults, this is IAM enforcement off (the
    emulator's own default) — byte-for-byte what the plain fixtures in ``conftest.py`` need.
    Passing both wires the container onto *network* and points it at the IAM control plane
    (``IAM_MODE=strict`` + ``IAM_EMULATOR_HOST=<iam_host>``) for the enforcement tests.
    """
    container = (
        DockerContainer(GCP_SECRET_MANAGER_EMULATOR_IMAGE)
        .with_bind_ports(grpc_port, grpc_port)
        .with_bind_ports(rest_port, rest_port)
    )
    if network is not None:
        container = container.with_network(network)
    if iam_host is not None:
        container = container.with_env("IAM_MODE", "strict").with_env("IAM_EMULATOR_HOST", iam_host)
    with container as c:
        yield c


def start_iam_emulator(network: Network, host_port: int) -> Generator[DockerContainer]:
    """Start the IAM control-plane emulator on *network*, bound to *host_port*, and yield it."""
    container = (
        DockerContainer(GCP_IAM_EMULATOR_IMAGE)
        .with_network(network)
        .with_network_aliases(IAM_NETWORK_ALIAS)
        .with_bind_ports(GCP_IAM_EMULATOR_INTERNAL_PORT, host_port)
    )
    with container as c:
        yield c


def grant_secret_manager_admin(iam_host_port: int, project_id: str, principal: str) -> None:
    """Bind *principal* to the built-in ``roles/secretmanager.admin`` role at project scope.

    Uses the IAM emulator's ``SetIamPolicy`` gRPC API directly — no ``policy.yaml`` to mount.
    ``roles/secretmanager.admin`` is a built-in role, so strict mode (which denies unknown
    roles) accepts it without further setup.
    """
    from google.iam.v1 import iam_policy_pb2, iam_policy_pb2_grpc, policy_pb2  # noqa: PLC0415

    channel = grpc.insecure_channel(f"localhost:{iam_host_port}")  # type: ignore[no-untyped-call]
    stub = iam_policy_pb2_grpc.IAMPolicyStub(channel)  # type: ignore[no-untyped-call]
    request = iam_policy_pb2.SetIamPolicyRequest(
        resource=f"projects/{project_id}",
        policy=policy_pb2.Policy(
            bindings=[policy_pb2.Binding(role="roles/secretmanager.admin", members=[principal])],
        ),
    )

    def _set_policy() -> None:
        stub.SetIamPolicy(request, timeout=5)

    retry_until_ready(_set_policy, grpc.RpcError)


class _PrincipalInterceptor(grpc.UnaryUnaryClientInterceptor, grpc.UnaryStreamClientInterceptor):
    """Appends an ``x-emulator-principal`` metadata entry to every outgoing call.

    ``GcpSecretManagerSource`` has no concept of a principal header — Application Default
    Credentials are its real-world auth path — so injecting this metadata purely at the test
    transport layer is the only way to drive the emulator's IAM enforcement in either
    direction (granted principal, or none at all).
    """

    def __init__(self, principal: str) -> None:
        self._principal = principal

    def _add_metadata(self, client_call_details: Any) -> Any:
        metadata = list(client_call_details.metadata or [])
        metadata.append(("x-emulator-principal", self._principal))
        return client_call_details._replace(metadata=metadata)

    def intercept_unary_unary(self, continuation: Any, client_call_details: Any, request: Any) -> Any:
        return continuation(self._add_metadata(client_call_details), request)

    def intercept_unary_stream(self, continuation: Any, client_call_details: Any, request: Any) -> Any:
        return continuation(self._add_metadata(client_call_details), request)


def secret_manager_grpc_transport(grpc_port: int, *, principal: str | None = None) -> "object":
    """A ``SecretManagerServiceGrpcTransport`` pointed at the emulator's plaintext gRPC port.

    Blocked until the emulator accepts gRPC connections. The emulator requires no credentials,
    so a pre-built transport (rather than ``credentials=``) is the only way to reach it —
    ``SecretManagerServiceClient`` rejects a transport combined with credentials, which is why
    ``GcpSecretManagerSource`` treats the two as mutually exclusive.

    With *principal* set, every call carries an ``x-emulator-principal`` metadata entry —
    used against the IAM-enforced stack to prove a granted principal is let through. Left at
    the default, no such header is sent, which is exactly what production
    ``GcpSecretManagerSource`` traffic looks like.
    """
    from google.cloud.secretmanager_v1.services.secret_manager_service.transports import (  # noqa: PLC0415
        SecretManagerServiceGrpcTransport,
    )

    channel = grpc.insecure_channel(f"localhost:{grpc_port}")  # type: ignore[no-untyped-call]

    def _check_ready() -> None:
        grpc.channel_ready_future(channel).result(timeout=5)  # type: ignore[no-untyped-call]

    retry_until_ready(_check_ready, grpc.FutureTimeoutError)

    if principal is not None:
        channel = grpc.intercept_channel(channel, _PrincipalInterceptor(principal))  # type: ignore[no-untyped-call]

    return SecretManagerServiceGrpcTransport(channel=channel)
