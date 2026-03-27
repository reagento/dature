"""dature vs pydantic-settings — stdlib dataclasses, no vendor lock-in."""

from dataclasses import dataclass
from pathlib import Path

from dature import Source, load

SOURCES_DIR = Path(__file__).parent / "sources"


# --8<-- [start:basic]
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(Source(file_=SOURCES_DIR / "pydantic_settings_basic.yaml"), Config)
# config.hostt → AttributeError immediately
# config.port is always int — guaranteed
# --8<-- [end:basic]

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is True
