"""Tests for TOML-specific loader functions."""

from datetime import time

import pytest

from dature.loaders.toml_ import time_passthrough


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (time(0, 0, 0), time(0, 0, 0)),
        (time(0, 0), time(0, 0)),
    ],
)
def test_time_passthrough(input_value, expected):
    assert time_passthrough(input_value) == expected
