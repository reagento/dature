"""field_mapping — explicit field renaming with F objects."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class DbConfig:
    database_url: str
    secret_key: str
    pool_size: int


config = load(
    LoadMetadata(
        file_=SOURCES_DIR / "naming_field_mapping.yaml",
        field_mapping={
            F[DbConfig].database_url: "db_url",
            F[DbConfig].secret_key: "key",
            F[DbConfig].pool_size: "pool",
        },
    ),
    DbConfig,
)

print(f"database_url: {config.database_url}")  # database_url: postgresql://localhost:5432/mydb
print(f"secret_key: {config.secret_key}")  # secret_key: my-secret-key
print(f"pool_size: {config.pool_size}")  # pool_size: 10
