"""@load() decorator — load config from environment variables."""

import os
from dataclasses import dataclass

from dature import LoadMetadata, load

os.environ["APP_HOST"] = "0.0.0.0"
os.environ["APP_PORT"] = "8080"
os.environ["APP_DEBUG"] = "true"
os.environ["APP_WORKERS"] = "4"


@load(LoadMetadata(prefix="APP_"))
@dataclass
class AppConfig:
    host: str
    port: int
    debug: bool
    workers: int


config = AppConfig()

assert config.host == "0.0.0.0"
assert config.port == 8080
assert config.debug is True
assert config.workers == 4
