"""Global dature.configure() — customize masking, error display, loading defaults."""

from dataclasses import dataclass
from pathlib import Path

import dature
from dature.config import LoadingConfig

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# 1. Default config — debug is off, no report
config = dature.load(dature.Source(file=SHARED_DIR / "common_app.yaml"), dataclass_=Config)
report = dature.get_load_report(config)
assert report is None

# 2. Enable debug globally via dature.configure()
dature.configure(loading=LoadingConfig(debug=True))

config = dature.load(dature.Source(file=SHARED_DIR / "common_app.yaml"), dataclass_=Config)
report = dature.get_load_report(config)
assert report is not None

# 3. Reset to defaults — debug is off again
dature.configure(loading=LoadingConfig())

config = dature.load(dature.Source(file=SHARED_DIR / "common_app.yaml"), dataclass_=Config)
report = dature.get_load_report(config)
assert report is None
