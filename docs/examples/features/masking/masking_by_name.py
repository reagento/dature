# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import dature

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [end:setup]

# --8<-- [start:example]
@dataclass
class Config:
    password: Literal["admin", "root"]
    host: str

dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_by_name.yaml"),
    schema=Config,
)
# --8<-- [end:example]
