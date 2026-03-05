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
config2 = CachedConfig()  # type: ignore[call-arg]

print(f"same instance (cached): {config1 is config2}")  # same instance (cached): True

os.environ["NOCACHE_HOST"] = "localhost"
os.environ["NOCACHE_PORT"] = "6379"


@load(LoadMetadata(prefix="NOCACHE_"), cache=False)
@dataclass
class UncachedConfig:
    host: str
    port: int


config3 = UncachedConfig()  # type: ignore[call-arg]
config4 = UncachedConfig()  # type: ignore[call-arg]

print(f"same instance (uncached): {config3 is config4}")  # same instance (uncached): False
