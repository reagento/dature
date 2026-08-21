from pathlib import Path

SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# 1. Default behavior (debug off = no report)
config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.load_report(config)
assert report is None

# 2. Enable debug via a Dature instance
conf = dature.Dature(loading={"debug": True})
config = conf.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.load_report(config)
assert report is not None

# 3. Different instance resets to defaults
conf2 = dature.Dature()
config = conf2.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.load_report(config)
assert report is None
# --8<-- [end:example]
