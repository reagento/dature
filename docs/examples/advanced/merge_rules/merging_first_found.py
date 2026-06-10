# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "merging_first_found_primary.yaml"),
    dature.Yaml12Source(file=SOURCES_DIR / "merging_first_found_fallback.yaml"),
    schema=Config,
    strategy="first_found",
)

assert config.host == "production-host"
assert config.port == 8080

# --8<-- [end:example]
