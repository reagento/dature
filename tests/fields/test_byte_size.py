import operator
from collections.abc import Callable

import pytest

from dature.fields.byte_size import ByteSize


class TestByteSize:
    @pytest.mark.parametrize(
        ("input_value", "expected_bytes"),
        [
            ("1.5 GB", 1_500_000_000),
            ("1 KiB", 1024),
            ("1024", 1024),
            ("0 B", 0),
            ("500 MB", 500_000_000),
            ("2.5 GiB", int(2.5 * 2**30)),
            ("1 TB", 1_000_000_000_000),
        ],
    )
    def test_parse(self, input_value: str, expected_bytes: int) -> None:
        assert int(ByteSize(input_value)) == expected_bytes

    def test_from_int(self) -> None:
        bs = ByteSize(1024)
        assert int(bs) == 1024

    @pytest.mark.parametrize(
        ("value", "decimal", "expected"),
        [
            (1024, False, "1KiB"),
            (2**20, False, "1MiB"),
            (2**30, False, "1GiB"),
            (0, False, "0B"),
            (1000, True, "1KB"),
            (1_000_000, True, "1MB"),
            (1_500_000_000, True, "1.5GB"),
        ],
    )
    def test_human_readable(self, value: int, decimal: bool, expected: str) -> None:
        assert ByteSize(value).human_readable(decimal=decimal) == expected

    def test_str(self) -> None:
        assert str(ByteSize(1024)) == "1KiB"

    def test_repr(self) -> None:
        assert repr(ByteSize(1024)) == "ByteSize(1024)"

    def test_eq(self) -> None:
        assert ByteSize(1024) == ByteSize(1024)
        assert ByteSize(1024) != ByteSize(2048)

    def test_hash(self) -> None:
        assert hash(ByteSize(1024)) == hash(ByteSize(1024))

    @pytest.mark.parametrize(
        ("left", "right", "op"),
        [
            (100, 200, operator.lt),
            (200, 100, operator.gt),
            (100, 200, operator.le),
            (100, 100, operator.le),
            (200, 100, operator.ge),
            (100, 100, operator.ge),
        ],
    )
    def test_comparison_true(
        self,
        left: int,
        right: int,
        op: Callable[[ByteSize, ByteSize], bool],
    ) -> None:
        assert op(ByteSize(left), ByteSize(right))

    @pytest.mark.parametrize(
        ("left", "right", "op"),
        [
            (200, 100, operator.lt),
            (100, 200, operator.gt),
        ],
    )
    def test_comparison_false(
        self,
        left: int,
        right: int,
        op: Callable[[ByteSize, ByteSize], bool],
    ) -> None:
        assert not op(ByteSize(left), ByteSize(right))

    @pytest.mark.parametrize(
        ("value", "error_match"),
        [
            ("not a size", "Invalid byte size"),
            ("100 XB", "Unknown unit"),
        ],
    )
    def test_invalid(self, value: str, error_match: str) -> None:
        with pytest.raises(ValueError, match=error_match):
            ByteSize(value)

    @pytest.mark.parametrize(
        "value",
        [-1, -1024],
    )
    def test_negative_int_raises(self, value: int) -> None:
        # Regression: ByteSize(-5) (from int) used to construct silently, while the
        # equivalent string form ByteSize("-5B") already raised — an asymmetry that
        # could mask configuration bugs.
        with pytest.raises(ValueError, match=r"^Byte size cannot be negative: .+$") as exc_info:
            ByteSize(value)

        assert str(exc_info.value) == f"Byte size cannot be negative: {value!r}"
