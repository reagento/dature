# --8<-- [start:setup]
import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ["APP_CONFIG_PATH"] = str(
    Path(__file__).parent / "sources" / "app.json"
)


@dataclass
class AppConfig:
    host: str = "localhost"
    port: int = 8080

# --8<-- [end:setup]

# --8<-- [start:example]
cfg = dature.load(
    dature.JsonSource(file="${@env.config_path}"),
    dature.EnvSource(prefix="APP_"),
    schema=AppConfig,
)

assert cfg.host == "db.internal"
assert cfg.port == 5432

# --8<-- [end:example]
