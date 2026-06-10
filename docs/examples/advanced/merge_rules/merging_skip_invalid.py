# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int = 3000


# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "merging_skip_invalid_defaults.yaml",
        skip_field_if_invalid=True,
    ),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 3000  # filled with default value

# --8<-- [end:example]
