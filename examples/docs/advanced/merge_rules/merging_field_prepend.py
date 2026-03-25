"""Per-field merge — PREPEND puts override list before base list."""

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
        field_merges=(MergeRule(F[Config].tags, FieldMergeStrategy.PREPEND),),
    ),
    Config,
)

assert config.tags == ["web", "api", "web", "default"]
assert config.tags == ["web", "api", "web", "default"]
