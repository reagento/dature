"""Tests for the abstract CliSource base class."""

import pytest

from dature import CliSource


class TestCliSourceAbstract:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            CliSource()  # type: ignore[abstract]
