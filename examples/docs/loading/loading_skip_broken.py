"""Loading recovery — skip a missing source and fall back to the next one."""

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
    dature.Yaml12Source(
        file=SOURCES_DIR / "does_not_exist.yaml",
        skip_if_broken=True,
    ),
    dature.Yaml12Source(file=SOURCES_DIR / "fallback.yaml"),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
