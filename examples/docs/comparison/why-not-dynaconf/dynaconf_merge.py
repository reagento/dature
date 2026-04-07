"""dature vs Dynaconf — explicit merge strategies in code."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


# --8<-- [start:merge]
config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "dynaconf_merge_defaults.yaml"),
    dature.Yaml12Source(file=SOURCES_DIR / "dynaconf_merge_local.yaml", skip_if_broken=True),
    schema=Config,
    strategy="last_wins",
)
# --8<-- [end:merge]

assert config.host == "localhost"
assert config.port == 9090
