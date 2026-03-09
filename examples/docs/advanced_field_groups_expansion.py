"""Field groups — nested dataclass expansion."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldGroup, LoadMetadata, MergeMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    host: str
    port: int
    database: Database


# FieldGroup(F[Config].database, F[Config].port)
# expands to (database.host, database.port, port)
config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SOURCES_DIR / "field_groups_nested_defaults.yaml"),
            LoadMetadata(file_=SOURCES_DIR / "field_groups_nested_overrides.yaml"),
        ),
        field_groups=(FieldGroup(F[Config].database, F[Config].port),),
    ),
    Config,
)

print(f"host: {config.host}")  # host: production.example.com
print(f"port: {config.port}")  # port: 8080
print(f"database.host: {config.database.host}")  # database.host: db.prod
print(f"database.port: {config.database.port}")  # database.port: 5433
