"""RAISE_ON_CONFLICT with per-field override."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = dature.load(
    dature.Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Source(file=SHARED_DIR / "common_overrides.yaml"),
    schema=Config,
    strategy="raise_on_conflict",
    field_merges={
        dature.F[Config].host: "last_wins",
        dature.F[Config].port: "last_wins",
        dature.F[Config].tags: "append_unique",
    },
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.tags == ["default", "web", "api"]
assert config.tags == ["default", "web", "api"]
assert config.tags == ["default", "web", "api"]
