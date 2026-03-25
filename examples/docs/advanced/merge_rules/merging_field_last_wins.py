"""Per-field merge — LAST_WINS keeps tags from the last source."""

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
        field_merges=(MergeRule(F[Config].tags, FieldMergeStrategy.LAST_WINS),),
    ),
    Config,
)

assert config.tags == ["web", "api"]
assert config.tags == ["web", "api"]
