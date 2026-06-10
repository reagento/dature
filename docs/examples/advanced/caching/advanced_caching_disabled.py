# --8<-- [start:setup]
import os
from dataclasses import dataclass

import dature

os.environ["NOCACHE_PORT"] = "6379"

# --8<-- [end:setup]

# --8<-- [start:example]
@dature.load(dature.EnvSource(prefix="NOCACHE_"), cache=False)
@dataclass
class UncachedConfig:
    port: int


config3 = UncachedConfig()
os.environ["NOCACHE_PORT"] = "9999"
config4 = UncachedConfig()

assert config3.port == 6379
assert config4.port == 9999

# --8<-- [end:example]
