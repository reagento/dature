import os
from dataclasses import dataclass

import dature

os.environ["APP__DATABASE"] = '{"host": "json-host", "port": "5432"}'

os.environ.pop("APP__DATABASE__HOST", None)
os.environ.pop("APP__DATABASE__PORT", None)


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database



config = dature.load(
    dature.EnvSource(prefix="APP__", nested_resolve_strategy="flat"),
    schema=Config,
)

# priority flat values not found -> parsing JSON
assert config.database.host == "json-host"
assert config.database.port == 5432

