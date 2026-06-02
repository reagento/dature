"""skip_broken_sources — continue loading when a source is missing."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"
SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Yaml12Source(
        file=SOURCES_DIR / "nonexistent.yaml",
        skip_if_broken=True,
    ),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 3000
assert config.debug is False
