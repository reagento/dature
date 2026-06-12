from pathlib import Path
SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

os.environ["APP_HOST"] = "env_localhost"

@dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.EnvSource(prefix="APP_"),
)
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = Config()
assert config.host == "env_localhost"
assert config.port == 3000
assert config.debug is False
# --8<-- [end:example]
