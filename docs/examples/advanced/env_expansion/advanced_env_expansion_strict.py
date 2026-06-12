from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

os.environ["APP_HOST"] = "https://api.example.com"


@dataclass
class Config:
    resolved_url: str
    fallback_url: str


config = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "advanced_env_expansion_strict.yaml",
        expand_env_vars="strict",
    ),
    schema=Config,
)

assert config.resolved_url == "https://api.example.com/api/v1"
assert config.fallback_url == "postgres://localhost:5432/dev"
# --8<-- [end:example]
