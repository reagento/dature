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
    host: str
    port: int
    database: Database


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "field_groups_nested_defaults.yaml"),
    dature.Yaml12Source(
        file=SOURCES_DIR
        / "advanced_field_groups_expansion_error_overrides.yaml",
    ),
    schema=Config,
    field_groups=(
        # F[Config].database expands to (database.host, database.port)
        # so this group resolves to (database.host, database.port, port)
        (dature.F[Config].database, dature.F[Config].port),
    ),
)
# --8<-- [end:example]
