"""Annotated validators — error example."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class ServiceConfig:
    port: Annotated[int, (V >= 1) & (V <= 65535)]
    name: Annotated[str, (V.len() >= 3) & (V.len() <= 50)]
    tags: Annotated[list[str], (V.len() >= 1) & V.unique_items()]
    workers: Annotated[int, V >= 1]


dature.load(
    dature.Json5Source(file=SOURCES_DIR / "validation_annotated_invalid.json5"),
    schema=ServiceConfig,
)
