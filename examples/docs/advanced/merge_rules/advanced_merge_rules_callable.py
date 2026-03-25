"""Callable merge — custom merge function for a field."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dature import F, Merge, MergeRule, MergeStrategy, Source, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


def merge_tags(values: list[Any]) -> list[str]:
    return sorted({v for lst in values for v in lst})


config = load(
    Merge(
        Source(file_=SHARED_DIR / "common_defaults.yaml"),
        Source(file_=SHARED_DIR / "common_overrides.yaml"),
        strategy=MergeStrategy.LAST_WINS,
        field_merges=(MergeRule(F[Config].tags, merge_tags),),
    ),
    Config,
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.tags == ["api", "default", "web"]
