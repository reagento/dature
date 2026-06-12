"""Function mode — load config from environment variables."""

import os
from dataclasses import dataclass

import dature

# (our externally-provided data for config)
os.environ["APP_HOST"] = "0.0.0.0"
os.environ["APP_PORT"] = "8080"
os.environ["APP_DEBUG"] = "true"


# Step 1: Define the config schema
@dataclass
class AppConfig:
    host: str
    port: int
    debug: bool = False

# Step 2: Load it!
config = dature.load(dature.EnvSource(prefix="APP_"), schema=AppConfig)

# PROFIT!
assert config.host == "0.0.0.0"
assert config.port == 8080
assert config.debug is True
