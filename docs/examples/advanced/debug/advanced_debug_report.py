from pathlib import Path

SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Yaml12Source(file=SHARED_DIR / "common_overrides.yaml"),
    schema=Config,
    field_merges={dature.F[Config].tags: "append"},
    debug=True,
)

report = dature.load_report(config)
assert report is not None

defaults_file = str(SHARED_DIR / "common_defaults.yaml")
overrides_file = str(SHARED_DIR / "common_overrides.yaml")
origins = report.field_origins
assert len(origins) == 3

assert origins[0].key == "host"
assert origins[0].value == "<REDACTED>"
assert len(origins[0].sources) == 1
assert origins[0].sources[0].source_index == 1
assert origins[0].sources[0].source_file == overrides_file

assert origins[1].key == "port"
assert origins[1].value == "<REDACTED>"
assert len(origins[1].sources) == 1
assert origins[1].sources[0].source_index == 1
assert origins[1].sources[0].source_file == overrides_file

assert origins[2].key == "tags"
assert origins[2].value == "<REDACTED>"
assert len(origins[2].sources) == 2
assert origins[2].sources[0].source_index == 0
assert origins[2].sources[0].source_file == defaults_file
assert origins[2].sources[1].source_index == 1
assert origins[2].sources[1].source_file == overrides_file
# --8<-- [end:example]
