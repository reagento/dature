"""Auto-mark every test under ``tests/integration/`` with ``@pytest.mark.integration``.

Also converts ``docker.errors.DockerException`` raised at fixture setup into a
``pytest.skip`` — covers both an unreachable daemon and registry-side failures
(e.g. corporate TLS interception blocking ``docker.io`` image pulls). CI runs
with a working Docker + registry, so this only fires in misconfigured envs.
"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest

# Cap testcontainers' container-startup wait at 30s (default 120). Vault dev mode
# starts in ~3-5s; 30s leaves headroom for image pull on a cold runner. Must be set
# before ``testcontainers.core.config`` is imported (its dataclass defaults read
# the env var once at class-body evaluation) — conftest runs before any test file
# that imports testcontainers, so this is safe here.
os.environ.setdefault("TC_MAX_TRIES", "30")

_INTEGRATION_ROOT = Path(__file__).parent.resolve()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if _INTEGRATION_ROOT in Path(item.fspath).resolve().parents:
            item.add_marker(pytest.mark.integration)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None]:  # noqa: ARG001
    from docker.errors import DockerException  # noqa: PLC0415

    try:
        return (yield)
    except DockerException as e:
        pytest.skip(f"Docker/registry unavailable: {e}")
