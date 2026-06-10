# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [end:setup]
# --8<-- [start:example]
@dataclass
class Config:
    host: str
    port: int

config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "hydra_defaults.yaml"),
    schema=Config,
)
assert isinstance(config, Config)

assert config.host == "localhost"
assert config.port == 8080
# --8<-- [end:example]
