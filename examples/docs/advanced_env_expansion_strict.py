"""ENV expansion — strict mode on LoadMetadata."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["BASE_URL"] = "https://api.example.com"
os.environ["SECRET_KEY"] = "my-secret-42"


@dataclass
class Config:
    api_url: str
    database_url: str
    secret: str
    price: str


config = load(
    LoadMetadata(file_=SOURCES_DIR / "env_expand.yaml", expand_env_vars="strict"),
    Config,
)

print(f"api_url: {config.api_url}")  # api_url: https://api.example.com/api/v1
print(f"database_url: {config.database_url}")  # database_url: postgres://localhost:5432/dev
print(f"secret: {config.secret}")  # secret: my-secret-42
print(f"price: {config.price}")  # price: $100
