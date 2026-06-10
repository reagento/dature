# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    port: Annotated[int, V >= 1]
# --8<-- [end:setup]

# --8<-- [start:example]
dature.load(
    dature.Json5Source(file=SOURCES_DIR / "error_format_config.json5"),
    schema=Config,
)
# --8<-- [end:example]
