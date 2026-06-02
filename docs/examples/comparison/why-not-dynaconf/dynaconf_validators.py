"""dature vs Dynaconf — inline Annotated validators."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: Annotated[int, (V > 0) & (V < 65536)]
    debug: bool = False


dature.load(
    dature.Toml11Source(file=SOURCES_DIR / "dynaconf_validators_invalid.toml"),
    schema=Config,
)
