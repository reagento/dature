"""Function mode — load config from environment variables."""

import os
from dataclasses import dataclass

from dature import LoadMetadata, load

os.environ["APP_HOST"] = "0.0.0.0"  # noqa: S104
os.environ["APP_PORT"] = "8080"
os.environ["APP_DEBUG"] = "true"


@dataclass
class AppConfig:
    host: str
    port: int
    debug: bool = False


config = load(LoadMetadata(prefix="APP_"), AppConfig)

print(f"host: {config.host}")  # host: 0.0.0.0
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: True
