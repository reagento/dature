"""Disable masking — mask_secrets=False exposes values in errors."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_key: Annotated[str, V.len() >= 20]
    host: str


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_per_source.yaml"),
    schema=Config,
    mask_secrets=False,
)
