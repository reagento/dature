"""Caching — decorator mode with cache disabled."""

import os
from dataclasses import dataclass

import dature

os.environ["NOCACHE_HOST"] = "localhost"
os.environ["NOCACHE_PORT"] = "6379"


@dature.load(dature.EnvSource(prefix="NOCACHE_"), cache=False)
@dataclass
class UncachedConfig:
    host: str
    port: int


config3 = UncachedConfig()
os.environ["NOCACHE_PORT"] = "9999"
config4 = UncachedConfig()
assert config3.port == 6379
assert config4.port == 9999
