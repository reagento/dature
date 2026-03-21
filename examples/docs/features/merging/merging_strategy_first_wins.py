"""FIRST_WINS — first source wins on conflict."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, MergeStrategy, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),
            LoadMetadata(file_=SHARED_DIR / "common_overrides.yaml"),
        ),
        strategy=MergeStrategy.FIRST_WINS,
    ),
    Config,
)

assert config.host == "localhost"
assert config.port == 3000
assert config.tags == ["default"]
