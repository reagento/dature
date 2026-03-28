"""Basic merging — Merge with two YAML sources."""

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
    dataclass_=Config,
    strategy=dature.MergeStrategy.LAST_WINS,
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.tags == ["web", "api"]
