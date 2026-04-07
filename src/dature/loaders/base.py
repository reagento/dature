import base64
import re
from datetime import timedelta
from urllib.parse import urlparse

from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.types import URL, Base64UrlBytes, Base64UrlStr

_TIMEDELTA_RE = re.compile(
    r"^(?:(?P<weeks>-?\d+)\s+weeks?(?:,\s*|\s+|$))?"
    r"(?:(?P<days>-?\d+)\s+days?(?:,\s*|\s+|$))?"
    r"(?:(?P<sign>-)?(?P<hours>\d+):(?P<minutes>\d{2})(?::(?P<seconds>\d{2})(?:\.(?P<microseconds>\d+))?)?)?$",
)


def bytes_from_string(value: str) -> bytes:
    return value.encode("utf-8")


def complex_from_string(value: str) -> complex:
    try:
        return complex(value.replace(" ", ""))
    except ValueError as exc:
        exc.input_value = value  # type: ignore[attr-defined]
        raise


def timedelta_from_string(value: str) -> timedelta:
    """Parse str(timedelta(...)) format: '1 day, 2:30:00', '2 days 1:02:03', '0:45:00', '2:30'."""
    match = _TIMEDELTA_RE.match(value)
    if match is None or value == "":
        exc = ValueError(f"Invalid timedelta format: {value!r}")
        exc.input_value = value  # type: ignore[attr-defined]
        raise exc

    groups = match.groupdict()
    microseconds = 0
    if groups["microseconds"] is not None:
        microseconds = int(groups["microseconds"].ljust(6, "0"))

    sign = -1 if groups["sign"] is not None else 1

    return timedelta(
        weeks=int(groups["weeks"] or 0),
        days=int(groups["days"] or 0),
        hours=sign * int(groups["hours"] or 0),
        minutes=sign * int(groups["minutes"] or 0),
        seconds=sign * int(groups["seconds"] or 0),
        microseconds=sign * microseconds,
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
    try:
        return PaymentCardNumber(value)
    except ValueError as exc:
        exc.input_value = value  # type: ignore[attr-defined]
        raise


def byte_size_from_string(value: str | int) -> ByteSize:
    try:
        return ByteSize(value)
    except ValueError as exc:
        exc.input_value = value  # type: ignore[attr-defined]
        raise
