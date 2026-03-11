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
            LoadMetadata(file_=SOURCES_DIR / "common_defaults.yaml"),
            LoadMetadata(file_=SOURCES_DIR / "common_overrides.yaml"),
        ),
        strategy=MergeStrategy.LAST_WINS,
    ),
    Config,
)

print(f"host: {config.host}")  # host: production.example.com
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: True
print(f"workers: {config.workers}")  # workers: 4
print(f"tags: {config.tags}")  # tags: ['web', 'api']
