"""Load from JSON5 file."""

from dataclasses import dataclass
from pathlib import Path

from dature import Source, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(Source(file=SOURCES_DIR / "intro_app.json5"), Config)

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
