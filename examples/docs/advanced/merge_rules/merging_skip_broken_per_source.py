"""skip_if_broken per source — override the global flag per Source."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"
SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = dature.load(
    dature.Source(file=SHARED_DIR / "common_defaults.yaml"),  # uses global
    dature.Source(
        file=SOURCES_DIR / "optional.yaml",
        skip_if_broken=True,
    ),  # always skip if broken
    dature.Source(
        file=SHARED_DIR / "common_overrides.yaml",
        skip_if_broken=False,
    ),  # never skip, even if global is True
    schema=Config,
    skip_broken_sources=True,  # global default
)

assert config.host == "production.example.com"
assert config.port == 8080
