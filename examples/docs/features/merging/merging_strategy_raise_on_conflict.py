"""RAISE_ON_CONFLICT — raises if the same key has different values."""

from dataclasses import dataclass
from pathlib import Path

from dature import Merge, MergeStrategy, Source, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool


config = load(
    Merge(
        (
            Source(file_=SHARED_DIR / "common_raise_on_conflict_a.yaml"),
            Source(file_=SHARED_DIR / "common_raise_on_conflict_b.yaml"),
        ),
        strategy=MergeStrategy.RAISE_ON_CONFLICT,
    ),
    Config,
)

# Disjoint keys — no conflict
assert config.host == "localhost"
assert config.port == 3000
assert config.debug is True
