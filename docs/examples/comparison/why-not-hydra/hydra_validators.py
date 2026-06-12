from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass
from typing import Annotated

import dature
from dature import V


@dataclass
class Config:
    host: str
    port: Annotated[int, (V > 0) & (V < 65536)] = 8080


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "hydra_validators_invalid.yaml"),
    schema=Config,
)
# --8<-- [end:example]
