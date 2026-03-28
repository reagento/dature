"""dature vs Hydra — returns your actual dataclass, not DictConfig."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


# --8<-- [start:dataclass]
config = dature.load(dature.Source(file=SOURCES_DIR / "hydra_defaults.yaml"), dataclass_=Config)
assert isinstance(config, Config)
# Full IDE support, type safety, __post_init__ works
# --8<-- [end:dataclass]

assert config.host == "localhost"
assert config.port == 8080
