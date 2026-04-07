import math
import re
from dataclasses import fields

from examples.all_types_dataclass import AllPythonTypesCompact


def assert_all_types_equal(result: AllPythonTypesCompact, expected: AllPythonTypesCompact) -> None:
    for field in fields(result):
        result_val = getattr(result, field.name)
        expected_val = getattr(expected, field.name)
        if (
            isinstance(result_val, float)
            and isinstance(expected_val, float)
            and math.isnan(result_val)
            and math.isnan(expected_val)
        ):
            continue
        if isinstance(result_val, re.Pattern) and isinstance(expected_val, re.Pattern):
            assert result_val.pattern == expected_val.pattern, (
                f"{field.name}: pattern {result_val.pattern!r} != {expected_val.pattern!r}"
            )
            assert result_val.flags == expected_val.flags, (
                f"{field.name}: flags {result_val.flags!r} != {expected_val.flags!r}"
            )
            continue
        assert result_val == expected_val, f"{field.name}: {result_val!r} != {expected_val!r}"
