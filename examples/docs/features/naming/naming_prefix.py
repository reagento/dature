"""prefix — filter ENV keys by prefix."""

import os
from dataclasses import dataclass

from dature import LoadMetadata, load

os.environ["MYAPP_HOST"] = "localhost"
os.environ["MYAPP_PORT"] = "9090"
os.environ["MYAPP_DEBUG"] = "true"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(LoadMetadata(prefix="MYAPP_"), Config)

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 9090
print(f"debug: {config.debug}")  # debug: True
