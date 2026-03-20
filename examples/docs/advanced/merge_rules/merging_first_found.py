"""FIRST_FOUND — use the first source that loads successfully."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, MergeStrategy, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SOURCES_DIR / "merging_first_found_primary.yaml"),
            LoadMetadata(file_=SOURCES_DIR / "merging_first_found_fallback.yaml"),
        ),
        strategy=MergeStrategy.FIRST_FOUND,
    ),
    Config,
)

assert config.host == "production-host"
assert config.port == 8080
