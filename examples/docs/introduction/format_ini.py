"""Load from INI file with section prefix."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = dature.load(
    dature.Source(file=SOURCES_DIR / "intro_app.ini", prefix="app"),
    dataclass_=Config,
)

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
