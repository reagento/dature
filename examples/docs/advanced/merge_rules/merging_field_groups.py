"""Field groups — ensure related fields change together."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, FieldGroup, Merge, Source, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    user: str
    password: str


config = load(
    Merge(
        Source(file=SHARED_DIR / "common_field_groups_defaults.yaml"),
        Source(file=SHARED_DIR / "common_field_groups_overrides.yaml"),
        field_groups=(FieldGroup(F[Config].host, F[Config].port),),
    ),
    Config,
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.user == "admin"
assert config.password == "secret"
