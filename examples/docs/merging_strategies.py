"""Merge strategies — LAST_WINS vs FIRST_WINS."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, MergeStrategy, load

SOURCES_DIR = Path(__file__).parent / "sources"


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
            LoadMetadata(file_=str(SOURCES_DIR / "defaults.yaml")),
            LoadMetadata(file_=str(SOURCES_DIR / "overrides.yaml")),
        ),
        strategy=MergeStrategy.LAST_WINS,
    ),
    Config,
)

first_wins = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=str(SOURCES_DIR / "defaults.yaml")),
            LoadMetadata(file_=str(SOURCES_DIR / "overrides.yaml")),
        ),
        strategy=MergeStrategy.FIRST_WINS,
    ),
    Config,
)

print(f"LAST_WINS  host: {last_wins.host}")
print(f"FIRST_WINS host: {first_wins.host}")
