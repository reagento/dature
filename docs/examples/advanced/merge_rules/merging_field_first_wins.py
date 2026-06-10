# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    tags: list[str]


# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "merging_field_base.yaml"),
    dature.Yaml12Source(file=SOURCES_DIR / "merging_field_override.yaml"),
    schema=Config,
    field_merges={dature.F[Config].tags: "first_wins"},  # UNIQUE(a + b, keep="first")
)

assert config.tags == ["web", "default"]
assert config.tags == ["web", "default"]

# --8<-- [end:example]
