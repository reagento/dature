"""Decorator mode — auto-load config on instantiation."""

import os
from dataclasses import dataclass

from dature import LoadMetadata, load

os.environ["APP_HOST"] = "0.0.0.0"
os.environ["APP_PORT"] = "8080"
os.environ["APP_DEBUG"] = "true"


@load(LoadMetadata(prefix="APP_"))
@dataclass
class AppConfig:
    host: str
    port: int
    debug: bool = False


config = AppConfig()

assert config.host == "0.0.0.0"
assert config.port == 8080
assert config.debug is True
