"""Loading error — every field is checked, all errors are reported together."""

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
    dature.Yaml12Source(file=SOURCES_DIR / "multiple_errors.yaml"),
    schema=Config,
)
