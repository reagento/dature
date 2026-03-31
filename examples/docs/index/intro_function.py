"""Function mode — load config from environment variables."""

import os
from dataclasses import dataclass

import dature

os.environ["APP_HOST"] = "0.0.0.0"
os.environ["APP_PORT"] = "8080"
os.environ["APP_DEBUG"] = "true"


@dataclass
class AppConfig:
    host: str
    port: int
    debug: bool = False


config = dature.load(dature.Source(prefix="APP_"), schema=AppConfig)

assert config.host == "0.0.0.0"
assert config.port == 8080
assert config.debug is True
