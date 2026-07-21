from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    name: str


config = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "naming_field_mapping_aliases.yaml",
        field_mapping={dature.F[Config].name: ("fullName", "userName")},
    ),
    schema=Config,
)

assert config.name == "Alice"  # fullName — first matching alias wins
# --8<-- [end:example]
