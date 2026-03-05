"""skip_broken_sources — continue loading when a source is missing."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=str(SOURCES_DIR / "defaults.yaml")),
            LoadMetadata(file_=str(SOURCES_DIR / "nonexistent.yaml"), skip_if_broken=True),
        ),
    ),
    Config,
)

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 3000
print(f"debug: {config.debug}")  # debug: False
