"""Global configure() via environment variables — DATURE_ prefix."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, configure, get_load_report, load
from dature.config import LoadingConfig

SHARED_DIR = Path(__file__).parents[2] / "shared"

# Set env vars before first load — dature reads DATURE_* on first use
os.environ["DATURE_LOADING__DEBUG"] = "true"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# 1. DATURE_LOADING__DEBUG=true — debug is on, report attached
config = load(LoadMetadata(file_=SHARED_DIR / "common_app.yaml"), Config)
report = get_load_report(config)
print(f"has report: {report is not None}")  # has report: True

# 2. Override env with configure() — debug is off
configure(loading=LoadingConfig(debug=False))

config = load(LoadMetadata(file_=SHARED_DIR / "common_app.yaml"), Config)
report = get_load_report(config)
print(f"has report: {report is not None}")  # has report: False

# 3. Reset to env defaults — debug is on again
configure(loading=LoadingConfig(debug=True))

config = load(LoadMetadata(file_=SHARED_DIR / "common_app.yaml"), Config)
report = get_load_report(config)
print(f"has report: {report is not None}")  # has report: True
