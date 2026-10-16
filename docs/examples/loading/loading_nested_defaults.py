from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class CacheConfig:
    ttl: int = 60
    enabled: bool = True


@dataclass
class Config:
    host: str
    cache: CacheConfig


config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "nested_defaults.yaml"),
    schema=Config,
)

assert config.host == "localhost"
assert config.cache == CacheConfig(ttl=60, enabled=True)
# --8<-- [end:example]
