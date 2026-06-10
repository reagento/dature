# --8<-- [start:setup]
import os
from dataclasses import dataclass

import dature

os.environ["CACHE_PORT"] = "6379"

# --8<-- [end:setup]

# --8<-- [start:example]
@dature.load(dature.EnvSource(prefix="CACHE_"), cache=True)
@dataclass
class CachedConfig:
    port: int


config1 = CachedConfig()
os.environ["CACHE_PORT"] = "9999"
config2 = CachedConfig()

assert config1.port == 6379
assert config2.port == 6379

# --8<-- [end:example]
