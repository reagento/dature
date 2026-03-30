"""FIRST_FOUND — use the first source that loads successfully."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


config = dature.load(
    dature.Source(file=SOURCES_DIR / "merging_first_found_primary.yaml"),
    dature.Source(file=SOURCES_DIR / "merging_first_found_fallback.yaml"),
    dataclass_=Config,
    strategy="first_found",
)

assert config.host == "production-host"
assert config.port == 8080
