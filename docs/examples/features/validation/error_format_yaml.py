"""Error format — YAML source."""

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
    dature.Yaml12Source(file=SOURCES_DIR / "error_format_config.yaml"),
    schema=Config,
)
