"""ENV variable expansion — all supported syntax variants."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["APP_HOST"] = "https://api.example.com"
os.environ["FALLBACK_DB_URL"] = "postgres://fallback:5432/db"


@dataclass
class Config:
    simple: str
    braced: str
    fallback_string: str
    fallback_var: str
    windows: str
    escape_dollar: str
    escape_percent: str


config = load(
    LoadMetadata(file_=SOURCES_DIR / "advanced_env_expansion.yaml", expand_env_vars="default"),
    Config,
)

print(f"simple: {config.simple}")  # simple: https://api.example.com
print(f"braced: {config.braced}")  # braced: https://api.example.com
print(f"fallback_string: {config.fallback_string}")  # fallback_string: postgres://localhost:5432/dev
print(f"fallback_var: {config.fallback_var}")  # fallback_var: postgres://fallback:5432/db
print(f"windows: {config.windows}")  # windows: https://api.example.com
print(f"escape_dollar: {config.escape_dollar}")  # escape_dollar: $100
print(f"escape_percent: {config.escape_percent}")  # escape_percent: 100%
