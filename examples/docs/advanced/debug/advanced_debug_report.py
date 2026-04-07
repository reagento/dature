"""Debug report — dature.get_load_report() to inspect which source provided each field."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Yaml12Source(file=SHARED_DIR / "common_overrides.yaml"),
    schema=Config,
    debug=True,
)

report = dature.get_load_report(config)
assert report is not None

origins = report.field_origins
assert len(origins) == 3

assert origins[0].key == "host"
assert origins[0].value == "production.example.com"
assert origins[0].source_index == 1
assert origins[0].source_file == str(SHARED_DIR / "common_overrides.yaml")

assert origins[1].key == "port"
assert origins[1].value == 8080
assert origins[1].source_index == 1
assert origins[1].source_file == str(SHARED_DIR / "common_overrides.yaml")

assert origins[2].key == "tags"
assert origins[2].value == ["web", "api"]
assert origins[2].source_index == 1
assert origins[2].source_file == str(SHARED_DIR / "common_overrides.yaml")
