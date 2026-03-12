"""Field groups — ensure related fields change together."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldGroup, LoadMetadata, MergeMetadata, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


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
            LoadMetadata(file_=SHARED_DIR / "common_field_groups_defaults.yaml"),
            LoadMetadata(file_=SHARED_DIR / "common_field_groups_overrides.yaml"),
        ),
        field_groups=(FieldGroup(F[Config].host, F[Config].port),),
    ),
    Config,
)

print(f"host: {config.host}")  # host: production.example.com
print(f"port: {config.port}")  # port: 8080
print(f"user: {config.user}")  # user: admin
print(f"password: {config.password}")  # password: secret
