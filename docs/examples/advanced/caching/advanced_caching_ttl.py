import os
import time
from dataclasses import dataclass
from datetime import timedelta

import dature

os.environ["TTL_PORT"] = "6379"

@dature.load(dature.EnvSource(prefix="TTL_"), cache=timedelta(seconds=30))
@dataclass
class TtlConfig:
    port: int


config1 = TtlConfig()
os.environ["TTL_PORT"] = "9999"

config2 = TtlConfig()

assert config1.port == 6379
assert config2.port == 6379

# Simulate TTL expiration by replacing the internal clock
real_monotonic = time.monotonic
time.monotonic = lambda: real_monotonic() + 60.0
config3 = TtlConfig()
time.monotonic = real_monotonic
assert config3.port == 9999
