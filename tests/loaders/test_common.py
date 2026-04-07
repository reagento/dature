"""Tests for common loader functions (used across multiple formats)."""

import math
from datetime import date, datetime, time

import pytest
from adaptix.load_error import TypeLoadError

from dature.loaders.common import (
    bool_loader,
    bytearray_from_json_string,
    bytearray_from_string,
    date_from_string,
    date_passthrough,
    datetime_from_string,
    datetime_passthrough,
    float_from_string,
    float_passthrough,
    int_from_string,
    none_from_empty_string,
    optional_from_empty_string,
    str_from_scalar,
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
    "input_value",
    ["10", "10:30:45:99", "abc"],
    ids=["one-part", "four-parts", "non-numeric"],
)
def test_time_from_string_invalid(input_value):
    with pytest.raises(ValueError, match="Invalid time format"):
        time_from_string(input_value)


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


def test_none_from_empty_string_non_empty_raises():
    with pytest.raises(TypeLoadError):
        none_from_empty_string("not empty")


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("", None),
        ("some text", "some text"),
    ],
)
def test_optional_from_empty_string(input_value, expected):
    assert optional_from_empty_string(input_value) == expected


# === str_from_scalar ===


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("hello", "hello"),
        (3.14, "3.14"),
        (True, "True"),
    ],
    ids=["string", "float", "bool"],
)
def test_str_from_scalar(input_value, expected):
    assert str_from_scalar(input_value) == expected


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


def test_bool_loader_invalid_string():
    with pytest.raises(TypeLoadError):
        bool_loader("maybe")


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
    [True, False, 3.14, 999.999, 0.0, -1.5],
)
def test_int_from_string_rejects_invalid(input_value):
    with pytest.raises(TypeLoadError):
        int_from_string(input_value)


def test_int_from_string_invalid_string():
    with pytest.raises(ValueError, match="invalid literal for int"):
        int_from_string("not-a-number")


# === Float passthrough ===


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (3.14, 3.14),
        (0.0, 0.0),
        (-1.5, -1.5),
        (float("inf"), float("inf")),
    ],
)
def test_float_passthrough(input_value, expected):
    assert float_passthrough(input_value) == expected


@pytest.mark.parametrize(
    "input_value",
    [True, False, 42, 0, -1],
)
def test_float_passthrough_rejects_invalid(input_value):
    with pytest.raises(TypeLoadError):
        float_passthrough(input_value)


# === Float from string ===


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("3.14", 3.14),
        ("inf", float("inf")),
        ("+inf", float("inf")),
        ("-inf", float("-inf")),
        (3.14, 3.14),
        (42, 42.0),
    ],
    ids=["string", "inf", "plus-inf", "minus-inf", "float-passthrough", "int-to-float"],
)
def test_float_from_string(input_value, expected):
    assert float_from_string(input_value) == expected


def test_float_from_string_nan():
    result = float_from_string("nan")
    assert math.isnan(result)


def test_float_from_string_invalid():
    with pytest.raises(ValueError, match="could not convert string to float"):
        float_from_string("not-a-number")


# === JSON string converters ===


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("hello", bytearray(b"hello")),
        ("", bytearray()),
        ("[72, 101, 108]", bytearray([72, 101, 108])),
        ('{"key": "val"}', bytearray(b'{"key": "val"}')),
    ],
    ids=["plain-string", "empty", "json-array", "non-bracket-string"],
)
def test_bytearray_from_json_string(input_value, expected):
    assert bytearray_from_json_string(input_value) == expected
