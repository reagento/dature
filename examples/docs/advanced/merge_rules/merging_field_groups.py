"""Field groups — ensure related fields change together."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    user: str
    password: str


config = dature.load(
    dature.Source(file=SHARED_DIR / "common_field_groups_defaults.yaml"),
    dature.Source(file=SHARED_DIR / "common_field_groups_overrides.yaml"),
    dataclass_=Config,
    field_groups=(dature.FieldGroup(dature.F[Config].host, dature.F[Config].port),),
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.user == "admin"
assert config.password == "secret"
