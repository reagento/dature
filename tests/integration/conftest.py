"""Auto-mark every test under ``tests/integration/`` with ``@pytest.mark.integration``.

Also converts ``docker.errors.DockerException`` raised at fixture setup into a
``pytest.skip`` — covers both an unreachable daemon and registry-side failures
(e.g. corporate TLS interception blocking ``docker.io`` image pulls). CI runs
with a working Docker + registry, so this only fires in misconfigured envs.
"""

from collections.abc import Generator
from pathlib import Path

import pytest

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
