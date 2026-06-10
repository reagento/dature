# --8<-- [start:setup]
import os
from dataclasses import dataclass

import dature

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


# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.EnvSource(
        prefix="APP__",
        nested_resolve={
            "json": (dature.F[Config].database,),
            "flat": (dature.F[Config].cache,),
        },
    ),
    schema=Config,
)

assert config.database.host == "json-host"
assert config.database.port == 5432
assert config.cache.host == "flat-cache"
assert config.cache.ttl == 120

# --8<-- [end:example]
