"""Field groups with nested dataclass — auto-expand nested fields."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldGroup, LoadMetadata, MergeMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    user: str
    password: str


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=str(SOURCES_DIR / "field_groups_defaults.yaml")),
            LoadMetadata(file_=str(SOURCES_DIR / "field_groups_overrides.yaml")),
        ),
        field_groups=(
            FieldGroup(F[Config].host, F[Config].port),
            FieldGroup(F[Config].user, F[Config].password),
        ),
    ),
    Config,
)

print(f"host: {config.host}")
print(f"port: {config.port}")
print(f"user: {config.user}")
print(f"password: {config.password}")
