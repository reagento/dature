"""Tuple shorthand — implicit LAST_WINS merge."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    workers: int
    tags: list[str]


config = load(
    (
        LoadMetadata(file_=SOURCES_DIR / "common_defaults.yaml"),
        LoadMetadata(file_=SOURCES_DIR / "common_overrides.yaml"),
    ),
    Config,
)

print(f"host: {config.host}")  # host: production.example.com
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: True
print(f"workers: {config.workers}")  # workers: 4
print(f"tags: {config.tags}")  # tags: ['web', 'api']
