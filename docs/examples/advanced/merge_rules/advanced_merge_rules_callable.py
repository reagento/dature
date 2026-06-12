from pathlib import Path

SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
from dataclasses import dataclass
from typing import Any

import dature


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


def merge_tags(values: list[Any]) -> list[str]:
    return sorted({v for lst in values for v in lst})


config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Yaml12Source(file=SHARED_DIR / "common_overrides.yaml"),
    schema=Config,
    strategy="last_wins",
    field_merges={dature.F[Config].tags: merge_tags},
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.tags == ["api", "default", "web"]
# --8<-- [end:example]
