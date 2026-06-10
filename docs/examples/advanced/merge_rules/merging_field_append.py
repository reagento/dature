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
    field_merges={dature.F[Config].tags: "append"},  # a + b
)

assert config.tags == ["web", "default", "web", "api"]
assert config.tags == ["web", "default", "web", "api"]

# --8<-- [end:example]
