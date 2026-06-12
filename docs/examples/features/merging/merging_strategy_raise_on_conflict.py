from pathlib import Path
SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int
    debug: bool

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_raise_on_conflict_a.yaml"),
    dature.Yaml12Source(file=SHARED_DIR / "common_raise_on_conflict_b.yaml"),
    schema=Config,
    strategy="raise_on_conflict",
)

assert config.host == "localhost"
assert config.port == 3000
assert config.debug is True
# --8<-- [end:example]
