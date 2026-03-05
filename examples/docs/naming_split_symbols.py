"""split_symbols — build nested structures from flat ENV variables."""

import os
from dataclasses import dataclass

from dature import LoadMetadata, load

os.environ["NS_DB__HOST"] = "localhost"
os.environ["NS_DB__PORT"] = "5432"


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    db: Database


config = load(LoadMetadata(prefix="NS_", split_symbols="__"), Config)

print(f"db.host: {config.db.host}")  # db.host: localhost
print(f"db.port: {config.db.port}")  # db.port: 5432
