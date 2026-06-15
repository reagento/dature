from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    password: str
    token: str


config = dature.load(
    dature.EnvFileSource(
        file=SOURCES_DIR / "naming_absolute_alias.env",
        prefix="APP_",
        field_mapping={
            dature.F[Config].host: "HOST",
            dature.F[Config].password: dature.Absolute("DB_PASSWORD"),
            dature.F[Config].token: ("TOKEN", dature.Absolute("DB_TOKEN")),
        },
    ),
    schema=Config,
)

assert config.host == "localhost"  # APP_HOST — prefix applied
assert config.password == "s3cr3t"  # DB_PASSWORD — prefix bypassed
assert config.token == "root-token"  # DB_TOKEN — Absolute in tuple
# --8<-- [end:example]
