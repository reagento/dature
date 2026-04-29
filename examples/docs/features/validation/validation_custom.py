"""Custom validator — error example using V.check as escape hatch."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class ServiceConfig:
    port: int
    name: str
    tags: list[str]
    workers: Annotated[
        int,
        (V >= 1)
        & V.check(
            lambda v: v % 2 == 0,
            error_message="Value must be divisible by 2",
        ),
    ]


dature.load(
    dature.Json5Source(file=SOURCES_DIR / "validation_custom_invalid.json5"),
    schema=ServiceConfig,
)
