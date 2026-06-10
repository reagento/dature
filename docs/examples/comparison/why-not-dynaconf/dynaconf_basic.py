# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False
# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Toml11Source(file=SOURCES_DIR / "dynaconf_basic.toml"),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
# --8<-- [end:example]
