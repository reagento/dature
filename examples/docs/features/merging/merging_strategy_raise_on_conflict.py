"""RAISE_ON_CONFLICT — raises if the same key has different values."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, MergeStrategy, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SHARED_DIR / "common_raise_on_conflict_a.yaml"),
            LoadMetadata(file_=SHARED_DIR / "common_raise_on_conflict_b.yaml"),
        ),
        strategy=MergeStrategy.RAISE_ON_CONFLICT,
    ),
    Config,
)

# Disjoint keys — no conflict
assert config.host == "localhost"
assert config.port == 3000
assert config.debug is True
