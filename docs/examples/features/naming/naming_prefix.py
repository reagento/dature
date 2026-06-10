# --8<-- [start:setup]
import os
from dataclasses import dataclass

import dature

os.environ["MYAPP_HOST"] = "localhost"
os.environ["MYAPP_PORT"] = "9090"
os.environ["MYAPP_DEBUG"] = "true"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False
# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(dature.EnvSource(prefix="MYAPP_"), schema=Config)

assert config.host == "localhost"
assert config.port == 9090
assert config.debug is True
# --8<-- [end:example]
