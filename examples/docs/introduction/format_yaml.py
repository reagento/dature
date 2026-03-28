"""Load from YAML file."""

from dataclasses import dataclass
from pathlib import Path

from dature import Source, load

SHARED_DIR = Path(__file__).parents[1] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(Source(file=SHARED_DIR / "common_app.yaml"), Config)

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
