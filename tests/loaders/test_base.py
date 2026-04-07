"""Tests for base loader functions (used only in BaseLoader defaults)."""

from datetime import timedelta
from urllib.parse import urlparse

import pytest

from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.loaders.base import (
    base64url_bytes_from_string,
    base64url_str_from_string,
    byte_size_from_string,
    bytes_from_string,
    complex_from_string,
    payment_card_number_from_string,
    secret_str_from_string,
    timedelta_from_string,
    url_from_string,
)


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("hello", b"hello"),
    ],
)
def test_bytes_from_string(input_value, expected):
    assert bytes_from_string(input_value) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("1+2j", 1 + 2j),
        ("1 + 2j", 1 + 2j),
    ],
    ids=["compact", "with-spaces"],
)
def test_complex_from_string(input_value, expected):
    assert complex_from_string(input_value) == expected


def test_complex_from_string_invalid():
    with pytest.raises(ValueError, match="complex\\(\\) arg is a malformed string"):
        complex_from_string("not-a-complex")


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("2:30", timedelta(hours=2, minutes=30)),
        ("2:30:00", timedelta(hours=2, minutes=30)),
        ("0:00:01", timedelta(seconds=1)),
        ("0:45:00", timedelta(minutes=45)),
        ("2:03:04.500000", timedelta(hours=2, minutes=3, seconds=4, microseconds=500000)),
        ("0:00:01.5", timedelta(seconds=1, microseconds=500000)),
        ("1 day, 2:30:00", timedelta(days=1, hours=2, minutes=30)),
        ("2 days, 0:00:00", timedelta(days=2)),
        ("1 day, 2:03:04.500000", timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=500000)),
        ("2 days 1:02:03.500000", timedelta(days=2, hours=1, minutes=2, seconds=3, microseconds=500000)),
        ("1 day 2:03:04.500000", timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=500000)),
        ("2 days 1:02:03", timedelta(days=2, hours=1, minutes=2, seconds=3)),
        ("1 day 2:30:00", timedelta(days=1, hours=2, minutes=30)),
        ("3 days", timedelta(days=3)),
        ("1 day", timedelta(days=1)),
        ("-1 day, 23:59:59", timedelta(days=-1, hours=23, minutes=59, seconds=59)),
        ("-2 days, 23:59:59", timedelta(days=-2, hours=23, minutes=59, seconds=59)),
        ("-1 day 23:59:59", timedelta(days=-1, hours=23, minutes=59, seconds=59)),
        ("-2 days 1:02:03", timedelta(days=-2, hours=1, minutes=2, seconds=3)),
        ("-2:30", timedelta(hours=-2, minutes=-30)),
        ("-0:00:01", timedelta(seconds=-1)),
        ("-2:03:04.500000", timedelta(hours=-2, minutes=-3, seconds=-4, microseconds=-500000)),
        ("1 week", timedelta(weeks=1)),
        ("2 weeks", timedelta(weeks=2)),
        ("-1 week", timedelta(weeks=-1)),
        ("-2 weeks", timedelta(weeks=-2)),
        ("1 week, 2:30:00", timedelta(weeks=1, hours=2, minutes=30)),
        ("2 weeks 1:02:03", timedelta(weeks=2, hours=1, minutes=2, seconds=3)),
        ("1 week 1 day", timedelta(weeks=1, days=1)),
        ("2 weeks, 3 days", timedelta(weeks=2, days=3)),
        ("1 week, 1 day, 2:30:00", timedelta(weeks=1, days=1, hours=2, minutes=30)),
        ("2 weeks 3 days 1:02:03", timedelta(weeks=2, days=3, hours=1, minutes=2, seconds=3)),
        ("-1 week, 1 day, 23:59:59", timedelta(weeks=-1, days=1, hours=23, minutes=59, seconds=59)),
        ("-2 weeks 1:02:03", timedelta(weeks=-2, hours=1, minutes=2, seconds=3)),
    ],
)
def test_timedelta_from_string(input_value: str, expected: timedelta):
    assert timedelta_from_string(input_value) == expected


@pytest.mark.parametrize(
    "input_value",
    ["not a timedelta", ""],
    ids=["invalid-text", "empty-string"],
)
def test_timedelta_from_string_invalid(input_value: str):
    with pytest.raises(ValueError, match="Invalid timedelta format"):
        timedelta_from_string(input_value)


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (
            "https://example.com/path?query=value#fragment",
            urlparse("https://example.com/path?query=value#fragment"),
        ),
        (
            "http://localhost:8080",
            urlparse("http://localhost:8080"),
        ),
        (
            "ftp://files.example.com/data.csv",
            urlparse("ftp://files.example.com/data.csv"),
        ),
    ],
)
def test_url_from_string(input_value: str, expected):
    assert url_from_string(input_value) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("SGVsbG8gV29ybGQ=", b"Hello World"),
        ("", b""),
        ("YWJj", b"abc"),
        ("-__-", b"\xfb\xff\xfe"),
    ],
)
def test_base64url_bytes_from_string(input_value: str, expected: bytes):
    assert base64url_bytes_from_string(input_value) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("SGVsbG8=", "Hello"),
        ("", ""),
        ("0L/RgNC40LLQtdGC", "\u043f\u0440\u0438\u0432\u0435\u0442"),
    ],
)
def test_base64url_str_from_string(input_value: str, expected: str):
    assert base64url_str_from_string(input_value) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("mysecret", SecretStr("mysecret")),
        ("", SecretStr("")),
    ],
)
def test_secret_str_from_string(input_value: str, expected: SecretStr):
    assert secret_str_from_string(input_value) == expected


@pytest.mark.parametrize(
    ("card_number", "expected_brand"),
    [
        ("4000000000000002", "Visa"),
        ("5100000000000008", "Mastercard"),
    ],
    ids=["visa", "mastercard"],
)
def test_payment_card_number_from_string(card_number, expected_brand: str):
    result = payment_card_number_from_string(card_number)
    assert isinstance(result, PaymentCardNumber)
    assert result.brand == expected_brand


def test_payment_card_number_from_string_invalid():
    with pytest.raises(ValueError, match="Card number must be 12-19 digits"):
        payment_card_number_from_string("1234")


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("1.5 GB", ByteSize(1_500_000_000)),
        (1024, ByteSize(1024)),
    ],
)
def test_byte_size_from_string(input_value: str | int, expected: ByteSize):
    assert byte_size_from_string(input_value) == expected


def test_byte_size_from_string_invalid():
    with pytest.raises(ValueError, match="Invalid byte size format"):
        byte_size_from_string("not-a-size")
