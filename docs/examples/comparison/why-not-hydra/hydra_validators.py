"""dature vs Hydra — Annotated validators for value constraints."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: Annotated[int, (V > 0) & (V < 65536)] = 8080


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "hydra_validators_invalid.yaml"),
    schema=Config,
)
