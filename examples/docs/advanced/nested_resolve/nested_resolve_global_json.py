"""Global nested_resolve_strategy="json" — use JSON value, ignore flat keys."""

import os
from dataclasses import dataclass

from dature import LoadMetadata, load
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


config = load(
    LoadMetadata(loader=EnvLoader, prefix="APP__", nested_resolve_strategy="json"),
    Config,
)

assert config.database.host == "json-host"
assert config.database.port == 5432
