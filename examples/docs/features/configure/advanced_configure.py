"""Global dature.configure() — customize masking, errors, loading."""

from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# 1. Default config — debug is off, no report
config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is None

# 2. Enable debug globally via dature.configure()
dature.configure(loading={"debug": True})

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is not None

# 3. Reset to defaults — debug is off again
dature.configure(loading={})

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is None
