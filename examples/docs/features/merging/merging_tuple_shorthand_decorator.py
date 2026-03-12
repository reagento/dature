"""Tuple shorthand as a decorator — implicit LAST_WINS merge."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SHARED_DIR = Path(__file__).parents[2] / "shared"

os.environ["APP_HOST"] = "env_localhost"


@load(
    (
        LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),
        LoadMetadata(prefix="APP_"),
    ),
)
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = Config()  # type: ignore[call-arg]
print(f"host: {config.host}")  # host: env_localhost
print(f"port: {config.port}")  # port: 3000
print(f"debug: {config.debug}")  # debug: False
