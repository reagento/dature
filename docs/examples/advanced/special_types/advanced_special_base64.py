"""Base64UrlBytes / Base64UrlStr — decoded from Base64."""

from base64 import urlsafe_b64decode
from dataclasses import dataclass

from dature.types import Base64UrlBytes, Base64UrlStr

encoded = "aGVsbG8gd29ybGQ="


@dataclass
class Config:
    token: Base64UrlStr
    data: Base64UrlBytes


config = Config(
    token=urlsafe_b64decode(encoded).decode(),
    data=urlsafe_b64decode(encoded),
)

assert config.token == "hello world"
assert type(config.token) is str
assert config.data == b"hello world"
assert type(config.data) is bytes
