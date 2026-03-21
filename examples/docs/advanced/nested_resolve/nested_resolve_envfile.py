"""nested_resolve_strategy with .env file source."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.sources_loader.env_ import EnvFileLoader

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database


config = load(
    LoadMetadata(
        file_=SOURCES_DIR / "nested_resolve.env",
        loader=EnvFileLoader,
        prefix="APP__",
        nested_resolve_strategy="json",
    ),
    Config,
)

assert config.database.host == "json-host"
assert config.database.port == 5432
