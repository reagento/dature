"""The problem: both JSON and flat keys exist for the same nested field."""

import os
from dataclasses import dataclass

import dature
from dature.sources_loader.env_ import EnvLoader

os.environ["APP__DATABASE"] = '{"host": "json-host", "port": "5432"}'
os.environ["APP__DATABASE__HOST"] = "flat-host"
os.environ["APP__DATABASE__PORT"] = "3306"


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database


# Without nested_resolve_strategy, flat keys win by default
config = dature.load(dature.Source(loader=EnvLoader, prefix="APP__"), schema=Config)

assert config.database.host == "flat-host"
assert config.database.port == 3306
