"""Decorator mode — explicit __init__ arguments take priority over loaded values."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[1] / "shared"


@dature.load(dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"))
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# --8<-- [start:override]
config = Config(port=9090)  # host from source, port overridden
# --8<-- [end:override]

assert config.host == "localhost"
assert config.port == 9090
