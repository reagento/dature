"""RAISE_ON_CONFLICT with per-field override."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldMergeStrategy, LoadMetadata, MergeMetadata, MergeRule, MergeStrategy, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


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
            LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),
            LoadMetadata(file_=SHARED_DIR / "common_overrides.yaml"),
        ),
        strategy=MergeStrategy.RAISE_ON_CONFLICT,
        field_merges=(
            MergeRule(F[Config].host, FieldMergeStrategy.LAST_WINS),
            MergeRule(F[Config].port, FieldMergeStrategy.LAST_WINS),
            MergeRule(F[Config].debug, FieldMergeStrategy.LAST_WINS),
            MergeRule(F[Config].workers, FieldMergeStrategy.LAST_WINS),
            MergeRule(F[Config].tags, FieldMergeStrategy.APPEND_UNIQUE),
        ),
    ),
    Config,
)

print(f"host: {config.host}")  # host: production.example.com
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: True
print(f"workers: {config.workers}")  # workers: 4
print(f"tags: {config.tags}")  # tags: ['default', 'web', 'api']
