from pathlib import Path

SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

# Env var enables debug by default
os.environ["DATURE_LOADING__DEBUG"] = "true"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# 1. Env enables debug → report is present
config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.load_report(config)
assert report is not None

# 2. A Dature instance can override the env — disabling debug explicitly
no_debug = dature.Dature(loading={"debug": False})
config = no_debug.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.load_report(config)
assert report is None

# 3. A second instance re-enables it (or rely on the env-derived default)
with_debug = dature.Dature(loading={"debug": True})
config = with_debug.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.load_report(config)
assert report is not None
# --8<-- [end:example]
