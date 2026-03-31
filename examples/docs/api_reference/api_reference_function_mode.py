"""Function mode — pass schema, get an instance back."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[1] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = dature.load(dature.Source(file=SHARED_DIR / "common_app.yaml"), schema=Config)

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
