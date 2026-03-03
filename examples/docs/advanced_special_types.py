"""Special types — URL, ByteSize, Base64UrlStr."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.fields.byte_size import ByteSize
from dature.types import URL, Base64UrlStr

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_url: URL
    max_upload: ByteSize
    token: Base64UrlStr


config = load(LoadMetadata(file_=str(SOURCES_DIR / "special_types.yaml")), Config)

print(f"api_url scheme: {config.api_url.scheme}")
print(f"api_url netloc: {config.api_url.netloc}")
print(f"max_upload: {int(config.max_upload)} bytes")
print(f"max_upload human: {config.max_upload.human_readable(decimal=True)}")
print(f"token: {config.token}")
