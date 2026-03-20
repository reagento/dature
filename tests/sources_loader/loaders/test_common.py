"""Tests for common loader functions (used across multiple formats)."""

from datetime import date, datetime, time

import pytest

from dature.sources_loader.loaders.common import (
    bool_loader,
    bytearray_from_json_string,
    bytearray_from_string,
    date_from_string,
    date_passthrough,
    datetime_from_string,
    datetime_passthrough,
    int_from_string,
    none_from_empty_string,
    optional_from_empty_string,
    time_from_string,
)

# === Date/Time converters ===


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("2024-12-31", date(2024, 12, 31)),
    ],
)
def test_date_from_string(input_value, expected):
    assert date_from_string(input_value) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("2024-12-31T23:59:59", datetime(2024, 12, 31, 23, 59, 59)),
    ],
)
def test_datetime_from_string(input_value, expected):
    assert datetime_from_string(input_value) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("10:30:45", time(10, 30, 45)),
        ("10:30", time(10, 30)),
    ],
)
def test_time_from_string(input_value, expected):
    assert time_from_string(input_value) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (date(2024, 12, 31), date(2024, 12, 31)),
    ],
)
def test_date_passthrough(input_value, expected):
    assert date_passthrough(input_value) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (datetime(2024, 12, 31, 23, 59, 59), datetime(2024, 12, 31, 23, 59, 59)),
    ],
)
def test_datetime_passthrough(input_value, expected):
    assert datetime_passthrough(input_value) == expected


# === string converters ===


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("hello", bytearray(b"hello")),
    ],
)
def test_bytearray_from_string(input_value, expected):
    assert bytearray_from_string(input_value) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("", None),
    ],
)
def test_none_from_empty_string(input_value, expected):
    assert none_from_empty_string(input_value) is expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("", None),
        ("some text", "some text"),
    ],
)
def test_optional_from_empty_string(input_value, expected):
    assert optional_from_empty_string(input_value) == expected


# === Bool converter ===


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),
        (True, True),
        (False, False),
    ],
)
def test_bool_loader(input_value, expected):
    assert bool_loader(input_value) is expected


# === Int converter ===


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (42, 42),
        ("42", 42),
        ("-1", -1),
        ("0", 0),
    ],
)
def test_int_from_string(input_value, expected):
    assert int_from_string(input_value) == expected


@pytest.mark.parametrize(
    "input_value",
    [True, False],
)
def test_int_from_string_rejects_bool(input_value):
    with pytest.raises(TypeError, match="Expected int, got bool"):
        int_from_string(input_value)


# === JSON string converters ===


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("hello", bytearray(b"hello")),
        ("", bytearray()),
    ],
)
def test_bytearray_from_json_string(input_value, expected):
    assert bytearray_from_json_string(input_value) == expected
