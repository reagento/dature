"""Global configure() via environment variables — DATURE_ prefix."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.config import _ConfigProxy

SOURCES_DIR = Path(__file__).parent / "sources"

# dature auto-loads DatureConfig from DATURE_* env vars on first use
os.environ["DATURE_MASKING__MASK_CHAR"] = "X"
os.environ["DATURE_MASKING__MIN_VISIBLE_CHARS"] = "1"
os.environ["DATURE_ERROR_DISPLAY__MAX_VISIBLE_LINES"] = "5"
os.environ["DATURE_LOADING__DEBUG"] = "false"

# Reset cached config so env vars are picked up
_ConfigProxy.set_instance(None)


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(LoadMetadata(file_=str(SOURCES_DIR / "app.yaml")), Config)

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 8080

# Cleanup
for key in list(os.environ):
    if key.startswith("DATURE_"):
        del os.environ[key]
_ConfigProxy.set_instance(None)
