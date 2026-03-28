"""Per-field merge — APPEND concatenates lists from all sources."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldMergeStrategy, Merge, MergeRule, Source, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    tags: list[str]


config = load(
    Merge(
        Source(file=SOURCES_DIR / "merging_field_base.yaml"),
        Source(file=SOURCES_DIR / "merging_field_override.yaml"),
        field_merges=(MergeRule(F[Config].tags, FieldMergeStrategy.APPEND),),
    ),
    Config,
)

assert config.tags == ["web", "default", "web", "api"]
assert config.tags == ["web", "default", "web", "api"]
