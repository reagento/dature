"""Heuristic masking — random tokens are masked in error messages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    connection_id: Literal["conn-1", "conn-2"]
    host: str


dature.load(
    dature.Source(file=SOURCES_DIR / "masking_heuristic.yaml", mask_secrets=True),
    schema=Config,
)
