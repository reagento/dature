import os
from pathlib import Path
import sys
SOURCES_DIR = Path(__file__).parent / "sources"
os.environ["APP_CONFIG_PATH"] = str(SOURCES_DIR / "app.json")

if sys.version_info < (3, 14):
    raise SystemExit("t-string syntax requires Python 3.14+")

# --8<-- [start:example]
from dataclasses import dataclass

import dature
from dature import ref


@dataclass
class AppConfig:
    host: str = "localhost"
    port: int = 8080


# t"{ref.env.config_path}"  ≡  "${@env.config_path}"
# t"{ref.env.log_level:INFO}"  ≡  "${@env.log_level:-INFO}"

cfg = dature.load(
    dature.JsonSource(file=t"{ref.env.config_path}"),
    dature.EnvSource(prefix="APP_"),
    schema=AppConfig,
)

assert cfg.host == "db.internal"
assert cfg.port == 5432
# --8<-- [end:example]