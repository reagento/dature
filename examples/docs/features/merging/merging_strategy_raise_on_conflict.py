"""RAISE_ON_CONFLICT — raises if the same key has different values."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool


config = dature.load(
    dature.Source(file=SHARED_DIR / "common_raise_on_conflict_a.yaml"),
    dature.Source(file=SHARED_DIR / "common_raise_on_conflict_b.yaml"),
    dataclass_=Config,
    strategy=dature.MergeStrategy.RAISE_ON_CONFLICT,
)

# Disjoint keys — no conflict
assert config.host == "localhost"
assert config.port == 3000
assert config.debug is True
