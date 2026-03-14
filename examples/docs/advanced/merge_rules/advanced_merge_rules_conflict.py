"""RAISE_ON_CONFLICT with per-field override."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldMergeStrategy, LoadMetadata, MergeMetadata, MergeRule, MergeStrategy, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
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
            MergeRule(F[Config].tags, FieldMergeStrategy.APPEND_UNIQUE),
        ),
    ),
    Config,
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.tags == ["default", "web", "api"]
