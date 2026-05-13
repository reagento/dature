"""
Caching — function mode reuses the result while the Source instance is alive.
"""

import os
from dataclasses import dataclass
from datetime import timedelta

import dature

os.environ["FN_HOST"] = "localhost"
os.environ["FN_PORT"] = "6379"


@dataclass
class FunctionConfig:
    host: str
    port: int


source = dature.EnvSource(prefix="FN_")


def get_config() -> FunctionConfig:
    return dature.load(
        source, schema=FunctionConfig, cache=timedelta(seconds=30)
    )


first = get_config()
os.environ["FN_PORT"] = "9999"
second = get_config()
assert first.port == 6379
assert second.port == 6379  # cache still fresh
