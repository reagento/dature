from pathlib import Path

SHARED_DIR = Path(__file__).parents[2] / "shared"
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = dature.load(
    dature.Yaml12Source(
        file=SHARED_DIR / "common_defaults.yaml",
    ),
    dature.Yaml12Source(
        file=SOURCES_DIR
        / "broken_config.yaml",  # per-source: skip parse errors
        skip_if_broken=True,
    ),
    dature.Yaml12Source(
        file=SOURCES_DIR
        / "local_overrides.yaml",  # per-source: skip if file absent
        skip_if_missing=True,
    ),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 3000
assert config.debug is False
# --8<-- [end:example]
