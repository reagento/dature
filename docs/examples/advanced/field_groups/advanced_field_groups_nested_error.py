"""Field groups — error on partial override (basic)."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"
SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    user: str
    password: str


dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_field_groups_defaults.yaml"),
    dature.Yaml12Source(
        file=SOURCES_DIR / "field_groups_partial_overrides.yaml",
    ),
    schema=Config,
    field_groups=(
        (dature.F[Config].host, dature.F[Config].port),
        (dature.F[Config].user, dature.F[Config].password),
    ),
)
