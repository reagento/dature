"""Load from TOML file."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:included]
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = dature.load(
    dature.Toml11Source(file=SOURCES_DIR / "intro_app.toml"),
    schema=Config,
)
# --8<-- [end:included]

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
