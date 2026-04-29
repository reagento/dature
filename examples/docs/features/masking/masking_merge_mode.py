"""Merge mode masking — secret_field_names applied across all sources."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    api_key: Annotated[str, V.len() >= 20] = ""


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_merge_mode_defaults.yaml"),
    dature.Yaml12Source(file=SOURCES_DIR / "masking_merge_mode_secrets.yaml"),
    schema=Config,
    secret_field_names=("api_key",),
)
