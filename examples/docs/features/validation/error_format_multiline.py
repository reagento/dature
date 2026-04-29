"""Error format — value spans multiple source lines."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    tags: Annotated[list[str], V.unique_items()]


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "error_format_multiline.yaml"),
    schema=Config,
)
