import logging
from pathlib import Path

logging.getLogger("dature").addHandler(logging.NullHandler())

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int
    timeout: int


dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "merging_skip_invalid_required_defaults.yaml",
        skip_field_if_invalid=(dature.F[Config].port,),
    ),
    dature.Yaml12Source(
        file=SOURCES_DIR / "merging_skip_invalid_required_overrides.yaml",
        skip_field_if_invalid=(dature.F[Config].port,),
    ),
    schema=Config,
)
# --8<-- [end:example]
