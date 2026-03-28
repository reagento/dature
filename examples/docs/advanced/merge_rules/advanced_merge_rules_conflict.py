"""RAISE_ON_CONFLICT with per-field override."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = dature.load(
    dature.Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Source(file=SHARED_DIR / "common_overrides.yaml"),
    dataclass_=Config,
    strategy=dature.MergeStrategy.RAISE_ON_CONFLICT,
    field_merges=(
        dature.MergeRule(dature.F[Config].host, dature.FieldMergeStrategy.LAST_WINS),
        dature.MergeRule(dature.F[Config].port, dature.FieldMergeStrategy.LAST_WINS),
        dature.MergeRule(dature.F[Config].tags, dature.FieldMergeStrategy.APPEND_UNIQUE),
    ),
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.tags == ["default", "web", "api"]
assert config.tags == ["default", "web", "api"]
assert config.tags == ["default", "web", "api"]
