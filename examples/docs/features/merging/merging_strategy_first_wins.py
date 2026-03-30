"""FIRST_WINS — first source wins on conflict."""

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
    dature.Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Source(file=SHARED_DIR / "common_overrides.yaml"),
    dataclass_=Config,
    strategy="first_wins",
)

assert config.host == "localhost"
assert config.port == 3000
assert config.tags == ["default"]
