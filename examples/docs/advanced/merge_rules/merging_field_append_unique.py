"""Per-field merge — APPEND_UNIQUE concatenates lists, removing duplicates."""

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
        field_merges=(MergeRule(F[Config].tags, FieldMergeStrategy.APPEND_UNIQUE),),
    ),
    Config,
)

assert config.tags == ["web", "default", "api"]
assert config.tags == ["web", "default", "api"]
