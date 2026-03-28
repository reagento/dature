"""Merge strategies — LAST_WINS vs FIRST_WINS."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


last_wins = dature.load(
    dature.Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Source(file=SHARED_DIR / "common_overrides.yaml"),
    dataclass_=Config,
    strategy=dature.MergeStrategy.LAST_WINS,
)

first_wins = dature.load(
    dature.Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Source(file=SHARED_DIR / "common_overrides.yaml"),
    dataclass_=Config,
    strategy=dature.MergeStrategy.FIRST_WINS,
)

assert last_wins.host == "production.example.com"
assert first_wins.host == "localhost"
