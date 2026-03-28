"""Per-field merge — LAST_WINS keeps tags from the last source."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    tags: list[str]


config = dature.load(
    dature.Source(file=SOURCES_DIR / "merging_field_base.yaml"),
    dature.Source(file=SOURCES_DIR / "merging_field_override.yaml"),
    dataclass_=Config,
    field_merges=(dature.MergeRule(dature.F[Config].tags, dature.FieldMergeStrategy.LAST_WINS),),
)

assert config.tags == ["web", "api"]
assert config.tags == ["web", "api"]
