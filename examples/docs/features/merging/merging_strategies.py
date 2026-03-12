"""Merge strategies — LAST_WINS vs FIRST_WINS."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, MergeStrategy, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    workers: int
    tags: list[str]


last_wins = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),
            LoadMetadata(file_=SHARED_DIR / "common_overrides.yaml"),
        ),
        strategy=MergeStrategy.LAST_WINS,
    ),
    Config,
)

first_wins = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),
            LoadMetadata(file_=SHARED_DIR / "common_overrides.yaml"),
        ),
        strategy=MergeStrategy.FIRST_WINS,
    ),
    Config,
)

print(f"LAST_WINS  host: {last_wins.host}")  # LAST_WINS  host: production.example.com
print(f"FIRST_WINS host: {first_wins.host}")  # FIRST_WINS host: localhost
