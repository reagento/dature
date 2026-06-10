# --8<-- [start:setup]
import os
from dataclasses import dataclass

import dature

os.environ["NS_DB__HOST"] = "localhost"
os.environ["NS_DB__PORT"] = "5432"


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    db: Database
# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.EnvSource(prefix="NS_", nested_sep="__"),
    schema=Config,
)

assert config.db.host == "localhost"
assert config.db.port == 5432
# --8<-- [end:example]
