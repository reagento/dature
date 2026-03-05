"""field_mapping + expand_env_vars — remap keys and substitute $ENV variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.field_path import F

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["DB_USER"] = "admin"
os.environ["DB_PASS"] = "s3cret"
os.environ["APP_SECRET_KEY"] = "my-secret-key-42"


@dataclass
class DbConfig:
    database_url: str
    secret_key: str
    pool_size: int


config = load(
    LoadMetadata(
        file_=str(SOURCES_DIR / "mapped.yaml"),
        field_mapping={
            F[DbConfig].database_url: "db_url",
            F[DbConfig].secret_key: "key",
            F[DbConfig].pool_size: "pool",
        },
        expand_env_vars="default",
    ),
    DbConfig,
)

print(f"database_url: {config.database_url}")  # database_url: postgresql://admin:s3cret@localhost:5432/mydb
print(f"secret_key: {config.secret_key}")  # secret_key: super-secret-key-123
print(f"pool_size: {config.pool_size}")  # pool_size: 10
