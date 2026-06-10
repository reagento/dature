# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[1] / "shared"


@dature.load(dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"))
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False
# --8<-- [end:setup]

# --8<-- [start:example]
config = Config(port=9090)

assert config.host == "localhost"
assert config.port == 9090
# --8<-- [end:example]
