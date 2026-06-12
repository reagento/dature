from pathlib import Path
SHARED_DIR = Path(__file__).parents[1] / "shared"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dature.load(dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"))
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = Config(port=9090)

assert config.host == "localhost"
assert config.port == 9090
# --8<-- [end:example]
