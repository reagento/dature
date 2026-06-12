from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database


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
