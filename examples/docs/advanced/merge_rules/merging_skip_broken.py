"""skip_broken_sources — continue loading when a source is missing."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"
SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),
            LoadMetadata(file_=SOURCES_DIR / "nonexistent.yaml", skip_if_broken=True),
        ),
    ),
    Config,
)

assert config.host == "localhost"
assert config.port == 3000
assert config.debug is False
