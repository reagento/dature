"""prefix — extract nested object from file sources using dot notation."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Database:
    host: str
    port: int


db = dature.load(
    dature.Source(file=SOURCES_DIR / "naming_prefix_nested.yaml", prefix="app.database"),
    dataclass_=Database,
)

assert db.host == "localhost"
assert db.port == 5432
