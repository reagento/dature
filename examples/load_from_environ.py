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


config = AppConfig()  # type: ignore[call-arg]

print(f"host: {config.host}")  # host: 0.0.0.0
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: True
print(f"workers: {config.workers}")  # workers: 4
