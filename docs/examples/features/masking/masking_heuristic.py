from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass
from typing import Literal

import dature


@dataclass
class Config:
    connection_id: Literal["conn-1", "conn-2"]
    host: str

dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_heuristic.yaml"),
    schema=Config,
)
# --8<-- [end:example]