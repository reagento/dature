"""Per-source masking — secret_field_names hides values in errors."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature.validators.string import MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_key: Annotated[str, MinLength(20)]
    host: str


dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "masking_per_source.yaml",
        secret_field_names=("api_key",),
    ),
    schema=Config,
)
