"""Global dature.configure() via environment variables — DATURE_ prefix."""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"

# Set env vars before first load — dature reads DATURE_* on first use
os.environ["DATURE_LOADING__DEBUG"] = "true"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# 1. DATURE_LOADING__DEBUG=true — debug is on, report attached
config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is not None

# 2. Override env with dature.configure() — debug is off
dature.configure(loading={"debug": False})

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is None

# 3. Reset to env defaults — debug is on again
dature.configure(loading={"debug": True})

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config,
)
report = dature.get_load_report(config)
assert report is not None
