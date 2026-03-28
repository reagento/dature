"""FIRST_WINS — first source wins on conflict."""

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
        strategy=MergeStrategy.FIRST_WINS,
    ),
    Config,
)

assert config.host == "localhost"
assert config.port == 3000
assert config.tags == ["default"]
