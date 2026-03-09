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
    card_number: str
    metadata: str


config = load(
    LoadMetadata(file_=SOURCES_DIR / "secrets.yaml", mask_secrets=True),
    Config,
    debug=True,
)

print(f"host: {config.host}")  # host: api.example.com
print(f"password: {config.password}")  # password: **********
print(f"api_key: {config.api_key}")  # api_key: **********
print(f"card_number: {config.card_number}")  # card_number: 4111111111111111
print(f"metadata: {config.metadata}")  # metadata: aK9$mP2xL5vQ8wR3nJ7yB4zT6
