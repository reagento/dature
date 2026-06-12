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
)

assert config.host == "production.example.com"
assert config.port == 8080
assert config.tags == ["web", "api"]
# --8<-- [end:example]
