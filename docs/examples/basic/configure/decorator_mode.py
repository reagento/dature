from pathlib import Path

SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
from dataclasses import dataclass

import dature

conf = dature.Dature(loading={"debug": True})


@conf.load(dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"))
@dataclass
class Settings:
    host: str
    port: int
    debug: bool = False


config = Settings()

assert config.host == "localhost"
assert config.port == 8080
assert dature.load_report(config) is not None
# --8<-- [end:example]
