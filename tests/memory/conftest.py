"""Fixtures for tests/memory — see tests/memory/helpers.py for the shared logic."""

from pathlib import Path

import pytest

from dature.sources.protocol import SourceProtocol
from tests.memory.helpers import SOURCE_BUILDERS


@pytest.fixture(params=sorted(SOURCE_BUILDERS))
def leak_source(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SourceProtocol:
    return SOURCE_BUILDERS[request.param](tmp_path, monkeypatch)
