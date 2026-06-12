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
    dature.Yaml12Source(file=SOURCES_DIR / "hydra_defaults.yaml"),
    dature.Toml11Source(
        file=SOURCES_DIR / "hydra_config.toml",
        skip_if_broken=True,
    ),
    dature.EnvSource(prefix="APP_"),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 9090
# --8<-- [end:example]
