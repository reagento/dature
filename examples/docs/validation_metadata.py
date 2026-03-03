"""Metadata validators — specify validators in LoadMetadata."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, LoadMetadata, load
from dature.validators.number import Ge, Lt
from dature.validators.string import MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(
    LoadMetadata(
        file_=str(SOURCES_DIR / "app.yaml"),
        validators={
            F[Config].host: MinLength(value=1),
            F[Config].port: (Ge(value=1), Lt(value=65536)),
        },
    ),
    Config,
)

print(f"host: {config.host}")
print(f"port: {config.port}")
