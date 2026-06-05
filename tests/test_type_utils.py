from dataclasses import dataclass
from typing import Annotated

import pytest

from dature.type_utils import find_nested_dataclasses


@dataclass
class _Inner:
    name: str


@pytest.mark.parametrize(
    ("input_type", "expected"),
    [
        (_Inner, [_Inner]),
        (list[_Inner], [_Inner]),
        (str, []),
        (_Inner | None, [_Inner]),
        (Annotated[_Inner, "some_meta"], [_Inner]),
        (dict[str, _Inner], [_Inner]),
        (list[_Inner | None], [_Inner]),
    ],
    ids=["plain-dc", "list-dc", "no-dc", "optional-dc", "annotated-dc", "dict-dc", "nested-generic"],
)
def test_find_nested_dataclasses(input_type: type, expected: list[type]) -> None:
    assert find_nested_dataclasses(input_type) == expected
