from pathlib import Path
import os

os.environ["APP_CONFIG_PATH"] = str(
    Path(__file__).parent / "sources" / "app.json"
)

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class AppConfig:
    host: str = "localhost"
    port: int = 8080


cfg = dature.load(
    dature.JsonSource(file="${@env.config_path}"),
    dature.EnvSource(prefix="APP_"),
    schema=AppConfig,
)

assert cfg.host == "db.internal"
assert cfg.port == 5432
# --8<-- [end:example]
