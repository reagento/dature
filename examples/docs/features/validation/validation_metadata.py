"""Metadata validators — error example."""

from dataclasses import dataclass
from pathlib import Path

import dature
from dature.validators.number import Ge, Lt
from dature.validators.string import MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "validation_metadata_invalid.yaml",
        validators={
            dature.F[Config].host: MinLength(1),
            dature.F[Config].port: (Ge(1), Lt(65536)),
        },
    ),
    schema=Config,
)
