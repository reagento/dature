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
report = dature.get_load_report(config)
assert report is None

# 2. Enable debug globally via runtime configuration
dature.configure(loading={"debug": True})

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is not None

# 3. Reset to defaults
dature.configure(loading={})

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is None
# --8<-- [end:example]