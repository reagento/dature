"""field_mapping — explicit field renaming with F objects."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class DbConfig:
    database_url: str
    secret_key: str
    pool_size: int


config = dature.load(
    dature.Source(
        file=SOURCES_DIR / "naming_field_mapping.yaml",
        field_mapping={
            dature.F[DbConfig].database_url: "db_url",
            dature.F[DbConfig].secret_key: "key",
            dature.F[DbConfig].pool_size: "pool",
        },
    ),
    schema=DbConfig,
)

assert config.database_url == "postgresql://localhost:5432/mydb"
assert config.secret_key == "my-secret-key"
assert config.pool_size == 10
