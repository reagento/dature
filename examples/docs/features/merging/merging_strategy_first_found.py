"""FIRST_FOUND — use the first source that loads successfully."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = dature.load(
    dature.Source(file=SHARED_DIR / "nonexistent.yaml"),
    dature.Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Source(file=SHARED_DIR / "common_overrides.yaml"),
    schema=Config,
    strategy="first_found",
)

# nonexistent.yaml is skipped, common_defaults.yaml is used entirely
assert config.host == "localhost"
assert config.port == 3000
assert config.tags == ["default"]
