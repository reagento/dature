# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database


# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.EnvFileSource(
        file=SOURCES_DIR / "nested_resolve.env",
        prefix="APP__",
        nested_resolve_strategy="json",
    ),
    schema=Config,
)

assert config.database.host == "json-host"
assert config.database.port == 5432

# --8<-- [end:example]
