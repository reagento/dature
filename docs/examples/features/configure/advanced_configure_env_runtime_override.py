import os
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"

# Env var affects initial behavior
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
report = dature.get_load_report(config)
assert report is not None

# 2. Runtime override disables debug (ignores env)
dature.configure(loading={"debug": False})

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is None

# 3. Reset to start behavior
dature.configure(loading={"debug": True})

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is not None