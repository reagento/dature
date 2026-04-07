"""Merge mode masking — Source.secret_field_names combined with Merge."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature.validators.string import MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    api_key: Annotated[str, MinLength(20)] = ""


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_merge_mode_defaults.yaml"),
    dature.Yaml12Source(
        file=SOURCES_DIR / "masking_merge_mode_secrets.yaml",
        secret_field_names=("api_key",),
    ),
    schema=Config,
)
