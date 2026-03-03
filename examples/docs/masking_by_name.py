"""Masking by name — auto-detect secrets by field name patterns."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_key: str
    password: str
    host: str


config = load(
    LoadMetadata(file_=str(SOURCES_DIR / "secrets.yaml"), mask_secrets=True),
    Config,
    debug=True,
)

print(f"host: {config.host}")
print(f"password: {config.password}")
print(f"api_key: {config.api_key}")
