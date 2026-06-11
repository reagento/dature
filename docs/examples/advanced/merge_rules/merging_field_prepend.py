from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    tags: list[str]


config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "merging_field_base.yaml"),
    dature.Yaml12Source(file=SOURCES_DIR / "merging_field_override.yaml"),
    schema=Config,
    field_merges={dature.F[Config].tags: "prepend"},  # b + a
)

assert config.tags == ["web", "api", "web", "default"]
# --8<-- [end:example]