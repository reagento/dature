"""Tuple shorthand as a decorator — implicit LAST_WINS merge."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import Source, load

SHARED_DIR = Path(__file__).parents[2] / "shared"

os.environ["APP_HOST"] = "env_localhost"


@load(
    (
        Source(file=SHARED_DIR / "common_defaults.yaml"),
        Source(prefix="APP_"),
    ),
)
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = Config()
assert config.host == "env_localhost"
assert config.port == 3000
assert config.debug is False
