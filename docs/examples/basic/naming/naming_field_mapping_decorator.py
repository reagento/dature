from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "naming_field_mapping_decorator.yaml",
        field_mapping={dature.F["Config"].database_url: "db_url"},
    ),
)
@dataclass
class Config:
    database_url: str


config = Config()

assert config.database_url == "postgresql://localhost:5432/mydb"
# --8<-- [end:example]
