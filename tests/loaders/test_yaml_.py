"""Tests for YAML-specific loader functions."""

from datetime import time

import pytest

from dature.loaders.yaml_ import time_from_int


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (0, time(0, 0, 0)),
        (86399, time(23, 59, 59)),
    ],
)
def test_time_from_int(input_value, expected):
    assert time_from_int(input_value) == expected
