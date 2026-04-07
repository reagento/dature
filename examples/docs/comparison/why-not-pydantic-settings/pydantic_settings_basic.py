"""dature vs pydantic-settings — stdlib dataclasses, no vendor lock-in."""

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


config = dature.load(dature.Yaml12Source(file=SOURCES_DIR / "pydantic_settings_basic.yaml"), schema=Config)
# config.hostt → AttributeError immediately
# config.port is always int — guaranteed
# --8<-- [end:basic]

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is True
