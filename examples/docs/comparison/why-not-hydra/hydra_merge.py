"""dature vs Hydra — multi-format merge."""

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
    dature.Yaml12Source(file=SOURCES_DIR / "hydra_defaults.yaml"),
    dature.Toml11Source(file=SOURCES_DIR / "hydra_config.toml", skip_if_broken=True),
    dature.EnvSource(prefix="APP_"),
    schema=Config,
)
# --8<-- [end:merge]

assert config.host == "localhost"
assert config.port == 9090
