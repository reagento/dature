"""Callable merge — custom merge function for a field."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dature import F, LoadMetadata, MergeMetadata, MergeRule, MergeStrategy, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    workers: int
    tags: list[str]


def merge_tags(values: list[Any]) -> list[str]:
    return sorted({v for lst in values for v in lst})


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SOURCES_DIR / "common_defaults.yaml"),
            LoadMetadata(file_=SOURCES_DIR / "common_overrides.yaml"),
        ),
        strategy=MergeStrategy.LAST_WINS,
        field_merges=(MergeRule(F[Config].tags, merge_tags),),
    ),
    Config,
)

print(f"host: {config.host}")  # host: production.example.com
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: True
print(f"workers: {config.workers}")  # workers: 4
print(f"tags: {config.tags}")  # tags: ['api', 'default', 'web']
