"""Caching — decorator mode with cache enabled."""

import os
from dataclasses import dataclass

import dature

os.environ["CACHE_HOST"] = "localhost"
os.environ["CACHE_PORT"] = "6379"


@dature.load(dature.Source(prefix="CACHE_"), cache=True)
@dataclass
class CachedConfig:
    host: str
    port: int


config1 = CachedConfig()
os.environ["CACHE_PORT"] = "9999"
config2 = CachedConfig()
assert config1.port == 6379
assert config2.port == 6379
