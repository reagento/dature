"""Basic merging — Merge with two YAML sources."""

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
        Source(file=SHARED_DIR / "common_defaults.yaml"),
        Source(file=SHARED_DIR / "common_overrides.yaml"),
        strategy=MergeStrategy.LAST_WINS,
    ),
    Config,
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.tags == ["web", "api"]
