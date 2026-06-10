# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"
SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(
        file=SHARED_DIR / "common_defaults.yaml",  # uses global
    ),
    dature.Yaml12Source(
        file=SOURCES_DIR / "optional.yaml",  # always skip, ignores global
        skip_if_broken=True,
    ),
    dature.Yaml12Source(
        file=SHARED_DIR / "common_overrides.yaml",  # never skip, ignores global
        skip_if_broken=False,
    ),
    schema=Config,
    skip_broken_sources=True,  # global default
)

assert config.host == "production.example.com"
assert config.port == 8080

# --8<-- [end:example]
