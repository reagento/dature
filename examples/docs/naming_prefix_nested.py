"""prefix — extract nested object from file sources using dot notation."""

from dataclasses import dataclass

from dature import LoadMetadata, load


@dataclass
class Database:
    host: str
    port: int


db = load(LoadMetadata(file_="examples/docs/sources/prefix_nested.yaml", prefix="app.database"), Database)

print(f"host: {db.host}")  # host: localhost
print(f"port: {db.port}")  # port: 5432
