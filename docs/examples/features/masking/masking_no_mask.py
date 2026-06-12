from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass
from typing import Annotated

import dature
from dature import V


@dataclass
class Config:
    api_key: Annotated[str, V.len() >= 20]
    host: str

dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_per_source.yaml"),
    schema=Config,
    mask_secrets=False,
)
# --8<-- [end:example]
