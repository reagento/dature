"""ENV variable expansion — all supported syntax variants."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import Source, load

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
    Source(file=SOURCES_DIR / "advanced_env_expansion.yaml", expand_env_vars="default"),
    Config,
)

assert config.simple == "https://api.example.com"
assert config.braced == "https://api.example.com"
assert config.fallback_string == "postgres://localhost:5432/dev"
assert config.fallback_var == "postgres://fallback:5432/db"
assert config.windows == "https://api.example.com"
assert config.escape_dollar == "$100"
assert config.escape_percent == "100%"
