"""Merge multiple sources — tuple-shorthand, LAST_WINS strategy."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"

DEFAULTS = LoadMetadata(file_=SOURCES_DIR / "defaults.toml")
OVERRIDES = LoadMetadata(file_=SOURCES_DIR / "overrides.toml")


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    workers: int
    tags: list[str]


config = load((DEFAULTS, OVERRIDES), Config)

print(f"host: {config.host}")  # host: 0.0.0.0
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: True
print(f"workers: {config.workers}")  # workers: 4
print(f"tags: {config.tags}")  # tags: ['web', 'api']
