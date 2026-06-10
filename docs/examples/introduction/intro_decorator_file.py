# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[1] / "shared"


# --8<-- [end:setup]

# --8<-- [start:example]
@dature.load(dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"))
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = Config()

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
# --8<-- [end:example]
