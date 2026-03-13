import base64
import re
from datetime import timedelta
from urllib.parse import urlparse

from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.types import URL, Base64UrlBytes, Base64UrlStr

_TIMEDELTA_WITH_DAYS_RE = re.compile(
    r"^(-?\d+)\s+days?,\s*(\d+):(\d{2}):(\d{2})(?:\.(\d+))?$",
)
_TIMEDELTA_TIME_ONLY_RE = re.compile(
    r"^(\d+):(\d{2}):(\d{2})(?:\.(\d+))?$",
)
_TIMEDELTA_TIME_ONLY_WITHOUT_SECONDS_RE = re.compile(
    r"^(\d+):(\d{2})?$",
)


def bytes_from_string(value: str) -> bytes:
    return value.encode("utf-8")


def complex_from_string(value: str) -> complex:
    return complex(value.replace(" ", ""))


def timedelta_from_string(value: str) -> timedelta:
    """Parse str(timedelta(...)) format: '1 day, 2:30:00', '0:45:00', '-1 day, 23:59:59'."""
    if match := _TIMEDELTA_WITH_DAYS_RE.match(value):
        days = int(match.group(1))
        hours = int(match.group(2))
        minutes = int(match.group(3))
        seconds = int(match.group(4))
        microseconds = int(match.group(5).ljust(6, "0")) if match.group(5) is not None else 0
        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds, microseconds=microseconds)

    if match := _TIMEDELTA_TIME_ONLY_RE.match(value):
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        microseconds = int(match.group(4).ljust(6, "0")) if match.group(4) is not None else 0
        return timedelta(hours=hours, minutes=minutes, seconds=seconds, microseconds=microseconds)

    if match := _TIMEDELTA_TIME_ONLY_WITHOUT_SECONDS_RE.match(value):
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return timedelta(hours=hours, minutes=minutes)

    msg = f"Invalid timedelta format: {value!r}"
    raise ValueError(msg)


def url_from_string(value: str) -> URL:
    return urlparse(value)


def base64url_bytes_from_string(value: str) -> Base64UrlBytes:
    return base64.urlsafe_b64decode(value)


def base64url_str_from_string(value: str) -> Base64UrlStr:
    return base64.urlsafe_b64decode(value).decode("utf-8")


def secret_str_from_string(value: str) -> SecretStr:
    return SecretStr(value)


def payment_card_number_from_string(value: str) -> PaymentCardNumber:
    return PaymentCardNumber(value)


def byte_size_from_string(value: str | int) -> ByteSize:
    return ByteSize(value)
