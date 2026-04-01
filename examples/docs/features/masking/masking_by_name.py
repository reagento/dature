"""Masking by name — secrets are masked in error messages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    password: Literal["admin", "root"]
    host: str


dature.load(dature.Source(file=SOURCES_DIR / "masking_by_name.yaml"), schema=Config)
