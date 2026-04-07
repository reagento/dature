"""dature vs Dynaconf — inline Annotated validators."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature.validators.number import Gt, Lt

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: Annotated[int, Gt(0), Lt(65536)]
    debug: bool = False


dature.load(dature.Toml11Source(file=SOURCES_DIR / "dynaconf_validators_invalid.toml"), schema=Config)
