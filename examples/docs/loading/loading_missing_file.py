"""Loading error — config file does not exist."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "does_not_exist.yaml"),
    schema=Config,
)
