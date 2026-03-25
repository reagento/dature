"""FIRST_FOUND — use the first source that loads successfully."""

from dataclasses import dataclass
from pathlib import Path

from dature import Merge, MergeStrategy, Source, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = load(
    Merge(
        (
            Source(file_=SHARED_DIR / "nonexistent.yaml"),
            Source(file_=SHARED_DIR / "common_defaults.yaml"),
            Source(file_=SHARED_DIR / "common_overrides.yaml"),
        ),
        strategy=MergeStrategy.FIRST_FOUND,
    ),
    Config,
)

# nonexistent.yaml is skipped, common_defaults.yaml is used entirely
assert config.host == "localhost"
assert config.port == 3000
assert config.tags == ["default"]
