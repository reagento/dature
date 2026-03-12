"""Caching — decorator mode with cache enabled/disabled."""

import os
from dataclasses import dataclass

from dature import LoadMetadata, load

os.environ["CACHE_HOST"] = "localhost"
os.environ["CACHE_PORT"] = "6379"


@load(LoadMetadata(prefix="CACHE_"), cache=True)
@dataclass
class CachedConfig:
    host: str
    port: int


config1 = CachedConfig()  # type: ignore[call-arg]
os.environ["CACHE_PORT"] = "9999"
config2 = CachedConfig()  # type: ignore[call-arg]

assert config1.port == 6379
assert config2.port == 6379

os.environ["NOCACHE_HOST"] = "localhost"
os.environ["NOCACHE_PORT"] = "6379"


@load(LoadMetadata(prefix="NOCACHE_"), cache=False)
@dataclass
class UncachedConfig:
    host: str
    port: int


config3 = UncachedConfig()  # type: ignore[call-arg]
os.environ["NOCACHE_PORT"] = "9999"
config4 = UncachedConfig()  # type: ignore[call-arg]

assert config3.port == 6379
assert config4.port == 9999
