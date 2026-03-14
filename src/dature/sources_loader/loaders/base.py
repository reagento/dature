import base64
import re
from datetime import timedelta
from urllib.parse import urlparse

from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.types import URL, Base64UrlBytes, Base64UrlStr

_TIMEDELTA_RE = re.compile(
    r"^(?:(?P<days>-?\d+)\s+days?(?:,\s*|\s+|$))?"
    r"(?:(?P<hours>\d+):(?P<minutes>\d{2})(?::(?P<seconds>\d{2})(?:\.(?P<microseconds>\d+))?)?)?$",
)


def bytes_from_string(value: str) -> bytes:
    return value.encode("utf-8")


def complex_from_string(value: str) -> complex:
    return complex(value.replace(" ", ""))


def timedelta_from_string(value: str) -> timedelta:
    """Parse str(timedelta(...)) format: '1 day, 2:30:00', '2 days 1:02:03', '0:45:00', '2:30'."""
    match = _TIMEDELTA_RE.match(value)
    if match is None or value == "":
        msg = f"Invalid timedelta format: {value!r}"
        raise ValueError(msg)

    groups = match.groupdict()
    microseconds = 0
    if groups["microseconds"] is not None:
        microseconds = int(groups["microseconds"].ljust(6, "0"))

    return timedelta(
        days=int(groups["days"] or 0),
        hours=int(groups["hours"] or 0),
        minutes=int(groups["minutes"] or 0),
        seconds=int(groups["seconds"] or 0),
        microseconds=microseconds,
    )


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
