"""Annotated validators — Ge, Le, MinLength, MaxLength, MinItems, UniqueItems."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from dature import LoadMetadata, load
from dature.validators.number import Ge, Le
from dature.validators.sequence import MinItems, UniqueItems
from dature.validators.string import MaxLength, MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class ServiceConfig:
    port: Annotated[int, Ge(value=1), Le(value=65535)]
    name: Annotated[str, MinLength(value=3), MaxLength(value=50)]
    tags: Annotated[list[str], MinItems(value=1), UniqueItems()]
    workers: Annotated[int, Ge(value=1)]


config = load(
    LoadMetadata(file_=SOURCES_DIR / "validated.json5"),
    ServiceConfig,
)

print(f"port: {config.port}")  # port: 8080
print(f"name: {config.name}")  # name: my-service
print(f"tags: {config.tags}")  # tags: ['web', 'api', 'production']
print(f"workers: {config.workers}")  # workers: 4
