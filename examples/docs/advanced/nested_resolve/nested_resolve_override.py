"""Per-field nested_resolve overrides global nested_resolve_strategy."""

import os
from dataclasses import dataclass

from dature import F, LoadMetadata, load
from dature.sources_loader.env_ import EnvLoader

os.environ["APP__DATABASE"] = '{"host": "json-host", "port": "5432"}'
os.environ["APP__DATABASE__HOST"] = "flat-host"
os.environ["APP__DATABASE__PORT"] = "3306"
os.environ["APP__CACHE"] = '{"host": "json-cache", "ttl": "60"}'
os.environ["APP__CACHE__HOST"] = "flat-cache"
os.environ["APP__CACHE__TTL"] = "120"


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Cache:
    host: str
    ttl: int


@dataclass
class Config:
    database: Database
    cache: Cache


# Global: "flat" for everything, but database overridden to "json"
config = load(
    LoadMetadata(
        loader=EnvLoader,
        prefix="APP__",
        nested_resolve_strategy="flat",
        nested_resolve={"json": (F[Config].database,)},
    ),
    Config,
)

assert config.database.host == "json-host"  # per-field override wins
assert config.database.port == 5432
assert config.cache.host == "flat-cache"  # global strategy
assert config.cache.ttl == 120
