"""Per-field merge — APPEND_UNIQUE concatenates lists, removing duplicates."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldMergeStrategy, LoadMetadata, MergeMetadata, MergeRule, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    tags: list[str]


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SOURCES_DIR / "merging_field_base.yaml"),
            LoadMetadata(file_=SOURCES_DIR / "merging_field_override.yaml"),
        ),
        field_merges=(MergeRule(F[Config].tags, FieldMergeStrategy.APPEND_UNIQUE),),
    ),
    Config,
)

assert config.tags == ["web", "default", "api"]
