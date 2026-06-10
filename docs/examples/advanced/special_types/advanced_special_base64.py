# --8<-- [start:setup]
from base64 import urlsafe_b64decode
from dataclasses import dataclass

from dature.type_aliases import Base64UrlBytes, Base64UrlStr

encoded = "aGVsbG8gd29ybGQ="


@dataclass
class Config:
    token: Base64UrlStr
    data: Base64UrlBytes


config = Config(
    token=urlsafe_b64decode(encoded).decode(),
    data=urlsafe_b64decode(encoded),
)

# --8<-- [end:setup]

# --8<-- [start:example]
assert config.token == "hello world"
assert type(config.token) is str
assert config.data == b"hello world"
assert type(config.data) is bytes

# --8<-- [end:example]
