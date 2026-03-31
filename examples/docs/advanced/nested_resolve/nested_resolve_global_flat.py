"""Global nested_resolve_strategy="flat" (default) — use flat keys, ignore JSON."""

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


config = dature.load(
    dature.Source(loader=EnvLoader, prefix="APP__", nested_resolve_strategy="flat"),
    schema=Config,
)

assert config.database.host == "flat-host"
assert config.database.port == 3306
