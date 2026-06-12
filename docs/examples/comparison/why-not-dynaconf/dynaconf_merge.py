from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int


config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "dynaconf_merge_defaults.yaml"),
    dature.Yaml12Source(
        file=SOURCES_DIR / "dynaconf_merge_local.yaml",
        skip_if_broken=True,
    ),
    schema=Config,
    strategy="last_wins",
)

assert config.host == "localhost"
assert config.port == 9090
# --8<-- [end:example]
