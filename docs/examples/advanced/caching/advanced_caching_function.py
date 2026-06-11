import os
from dataclasses import dataclass
from datetime import timedelta

import dature

os.environ["FN_PORT"] = "6379"


@dataclass
class FunctionConfig:
    port: int


loader = dature.Loader(
    dature.EnvSource(prefix="FN_"),
    schema=FunctionConfig,
    cache=timedelta(seconds=30),
)

first = loader.load()
os.environ["FN_PORT"] = "9999"
second = loader.load()

assert first.port == 6379
assert second.port == 6379  # cache still fresh — same Loader instance
