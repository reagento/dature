"""Load from JSON5 file."""

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
    dature.Json5Source(file=SOURCES_DIR / "intro_app.json5"),
    schema=Config,
)
# --8<-- [end:included]

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
