"""Tuple shorthand — implicit LAST_WINS merge."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = load(
    (
        LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),
        LoadMetadata(file_=SHARED_DIR / "common_overrides.yaml"),
    ),
    Config,
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.tags == ["web", "api"]
