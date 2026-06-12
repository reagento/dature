from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass
from typing import Literal

import dature


@dataclass
class Config:
    password: Literal["admin", "root"]
    host: str

dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_by_name.yaml"),
    schema=Config,
)
# --8<-- [end:example]
