"""FIRST_FOUND — use the first source that loads successfully."""

from dataclasses import dataclass
from pathlib import Path

from dature import Merge, MergeStrategy, Source, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


config = load(
    Merge(
        Source(file=SOURCES_DIR / "merging_first_found_primary.yaml"),
        Source(file=SOURCES_DIR / "merging_first_found_fallback.yaml"),
        strategy=MergeStrategy.FIRST_FOUND,
    ),
    Config,
)

assert config.host == "production-host"
assert config.port == 8080
