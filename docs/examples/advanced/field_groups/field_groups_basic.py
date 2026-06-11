from pathlib import Path
SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    user: str
    password: str


config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_field_groups_defaults.yaml"),
    dature.Yaml12Source(file=SHARED_DIR / "common_field_groups_overrides.yaml"),
    schema=Config,
    field_groups=((dature.F[Config].host, dature.F[Config].port),),
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.user == "admin"
assert config.password == "secret"
# --8<-- [end:example]