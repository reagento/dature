"""Per-field merge — APPEND_UNIQUE concatenates lists, removing duplicates."""

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
    field_merges={dature.F[Config].tags: "append_unique"},
)

assert config.tags == ["web", "default", "api"]
assert config.tags == ["web", "default", "api"]
