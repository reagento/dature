from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "multiple_errors.yaml"),
    schema=Config,
)
# --8<-- [end:example]
