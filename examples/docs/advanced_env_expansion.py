"""ENV variable expansion — $VAR, ${VAR:-default} syntax."""

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
    LoadMetadata(file_=str(SOURCES_DIR / "env_expand.yaml"), expand_env_vars="default"),
    Config,
)

print(f"api_url: {config.api_url}")
print(f"database_url: {config.database_url}")
print(f"secret: {config.secret}")
print(f"price: {config.price}")
