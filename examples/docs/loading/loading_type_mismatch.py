"""Loading error — value cannot be coerced to the field type."""

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
    dature.Yaml12Source(file=SOURCES_DIR / "type_mismatch.yaml"),
    schema=Config,
)
