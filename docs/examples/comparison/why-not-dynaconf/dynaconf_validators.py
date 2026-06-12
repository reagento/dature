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
    port: Annotated[int, (V > 0) & (V < 65536)]
    debug: bool = False

dature.load(
    dature.Toml11Source(file=SOURCES_DIR / "dynaconf_validators_invalid.toml"),
    schema=Config,
)
# --8<-- [end:example]
