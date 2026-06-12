from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature
from dature import V


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "validation_metadata_invalid.yaml",
        validators={
            dature.F[Config].host: V.len() >= 1,
            dature.F[Config].port: (V >= 1) & (V < 65536),
        },
    ),
    schema=Config,
)
# --8<-- [end:example]
