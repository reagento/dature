"""Error format — INI source."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    port: Annotated[int, V >= 1]


dature.load(
    dature.IniSource(
        file=SOURCES_DIR / "error_format_config.ini",
        prefix="app",
    ),
    schema=Config,
)
