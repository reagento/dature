# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [end:setup]

# --8<-- [start:example]

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
# --8<-- [end:example]
