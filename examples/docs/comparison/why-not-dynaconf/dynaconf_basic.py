"""dature vs Dynaconf — typed dataclass instead of dynamic access."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


# --8<-- [start:basic]
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = dature.load(dature.Source(file=SOURCES_DIR / "dynaconf_basic.toml"), dataclass_=Config)
# config.hostt → AttributeError immediately
# config.port is always int — guaranteed
# --8<-- [end:basic]

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
