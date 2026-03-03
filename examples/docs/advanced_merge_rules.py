"""Per-field merge rules — all FieldMergeStrategy options."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldMergeStrategy, LoadMetadata, MergeMetadata, MergeRule, MergeStrategy, load

SOURCES_DIR = Path(__file__).parent / "sources"


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
            LoadMetadata(file_=str(SOURCES_DIR / "defaults.yaml")),
            LoadMetadata(file_=str(SOURCES_DIR / "overrides.yaml")),
        ),
        strategy=MergeStrategy.LAST_WINS,
        field_merges=(
            MergeRule(F[Config].host, FieldMergeStrategy.FIRST_WINS),
            MergeRule(F[Config].tags, FieldMergeStrategy.APPEND_UNIQUE),
            MergeRule(F[Config].workers, max),
        ),
    ),
    Config,
)

print(f"host: {config.host}")
print(f"tags: {config.tags}")
print(f"workers: {config.workers}")
