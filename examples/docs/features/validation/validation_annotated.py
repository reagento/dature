"""Annotated validators — error example."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature.validators.number import Ge, Le
from dature.validators.sequence import MinItems, UniqueItems
from dature.validators.string import MaxLength, MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class ServiceConfig:
    port: Annotated[int, Ge(1), Le(65535)]
    name: Annotated[str, MinLength(3), MaxLength(50)]
    tags: Annotated[list[str], MinItems(1), UniqueItems()]
    workers: Annotated[int, Ge(1)]


dature.load(
    dature.Source(file=SOURCES_DIR / "validation_annotated_invalid.json5"),
    schema=ServiceConfig,
)
