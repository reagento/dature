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
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Yaml12Source(
        file=SOURCES_DIR / "broken_config.yaml",
    ),
    schema=Config,
    skip_if_broken=True,
)

assert config.host == "localhost"
assert config.port == 3000
assert config.debug is False
# --8<-- [end:example]
