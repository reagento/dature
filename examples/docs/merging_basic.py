"""Basic merging — MergeMetadata with two YAML sources."""

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


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=str(SOURCES_DIR / "defaults.yaml")),
            LoadMetadata(file_=str(SOURCES_DIR / "overrides.yaml")),
        ),
        strategy=MergeStrategy.LAST_WINS,
    ),
    Config,
)

print(f"host: {config.host}")
print(f"port: {config.port}")
print(f"debug: {config.debug}")
print(f"workers: {config.workers}")
print(f"tags: {config.tags}")
