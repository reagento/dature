"""Per-field merge — PREPEND_UNIQUE puts override before base, removing duplicates."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldMergeStrategy, Merge, MergeRule, Source, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    tags: list[str]


config = load(
    Merge(
        Source(file_=SOURCES_DIR / "merging_field_base.yaml"),
        Source(file_=SOURCES_DIR / "merging_field_override.yaml"),
        field_merges=(MergeRule(F[Config].tags, FieldMergeStrategy.PREPEND_UNIQUE),),
    ),
    Config,
)

assert config.tags == ["web", "api", "default"]
assert config.tags == ["web", "api", "default"]
