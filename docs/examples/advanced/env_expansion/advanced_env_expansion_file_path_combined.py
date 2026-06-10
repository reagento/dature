# --8<-- [start:setup]
import os
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["DATURE_SOURCES_DIR"] = str(SOURCES_DIR)
os.environ["DATURE_APP_ENV"] = "production"


@dataclass
class Config:
    host: str
    port: int


# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(file="$DATURE_SOURCES_DIR/config.$DATURE_APP_ENV.yaml"),
    schema=Config,
)

assert config.host == "prod.example.com"
assert config.port == 443

# --8<-- [end:example]
