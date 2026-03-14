"""ENV expansion — strict mode on LoadMetadata."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["APP_HOST"] = "https://api.example.com"


@dataclass
class Config:
    resolved_url: str
    fallback_url: str


config = load(
    LoadMetadata(file_=SOURCES_DIR / "advanced_env_expansion_strict.yaml", expand_env_vars="strict"),
    Config,
)

assert config.resolved_url == "https://api.example.com/api/v1"
assert config.fallback_url == "postgres://localhost:5432/dev"
