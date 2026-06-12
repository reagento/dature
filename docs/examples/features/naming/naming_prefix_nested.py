from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Database:
    host: str
    port: int

db = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "naming_prefix_nested.yaml",
        prefix="app.database",
    ),
    schema=Database,
)

assert db.host == "localhost"
assert db.port == 5432
# --8<-- [end:example]
