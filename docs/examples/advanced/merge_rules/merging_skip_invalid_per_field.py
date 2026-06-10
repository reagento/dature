# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    timeout: int


# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "merging_skip_invalid_per_field_defaults.yaml",
    ),
    dature.Yaml12Source(
        file=SOURCES_DIR / "merging_skip_invalid_per_field_overrides.yaml",
        skip_field_if_invalid=(dature.F[Config].port, dature.F[Config].timeout),
    ),
    schema=Config,
)

assert config.host == "production.example.com"
assert config.port == 3000
assert config.timeout == 30

# --8<-- [end:example]
