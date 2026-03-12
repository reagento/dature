"""prefix — extract nested object from file sources using dot notation."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Database:
    host: str
    port: int


db = load(LoadMetadata(file_=SOURCES_DIR / "naming_prefix_nested.yaml", prefix="app.database"), Database)

print(f"host: {db.host}")  # host: localhost
print(f"port: {db.port}")  # port: 5432
