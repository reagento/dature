"""Strategy is only a priority — if only one form exists, it is always used."""

import os
from dataclasses import dataclass

from dature import LoadMetadata, load
from dature.sources_loader.env_ import EnvLoader

# Only JSON form, no flat keys
os.environ["APP__DATABASE"] = '{"host": "json-host", "port": "5432"}'

# Make sure no flat keys interfere
os.environ.pop("APP__DATABASE__HOST", None)
os.environ.pop("APP__DATABASE__PORT", None)


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database


# Even with strategy="flat", JSON is parsed because there are no flat keys
config = load(
    LoadMetadata(loader=EnvLoader, prefix="APP__", nested_resolve_strategy="flat"),
    Config,
)

assert config.database.host == "json-host"
assert config.database.port == 5432
