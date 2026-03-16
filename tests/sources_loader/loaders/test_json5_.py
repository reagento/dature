"""Tests for json5_ loader functions."""

import pytest
from json5 import JsonIdentifier

from dature.sources_loader.loaders.json5_ import str_from_json_identifier


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (JsonIdentifier(""), ""),
        (JsonIdentifier("some_key"), "some_key"),
    ],
)
def test_str_from_json_identifier(input_value: JsonIdentifier, expected: str) -> None:
    assert str_from_json_identifier(input_value) == expected
