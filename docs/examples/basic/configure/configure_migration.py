from pathlib import Path

SHARED_DIR = Path(__file__).parents[2] / "shared"

from dataclasses import dataclass

import dature


@dataclass
class Settings:
    host: str
    port: int


# --8<-- [start:before]
dature.configure(vault={"host": "localhost", "port": 8200})
result = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"), schema=Settings
)
# --8<-- [end:before]

assert result.host == "localhost"
assert result.port == 8080

# --8<-- [start:after]
conf = dature.Dature(vault={"host": "localhost", "port": 8200})
result = conf.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"), schema=Settings
)
# --8<-- [end:after]

assert result.host == "localhost"
assert result.port == 8080
