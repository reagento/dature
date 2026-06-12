from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

os.environ["DATURE_SOURCES_DIR"] = str(SOURCES_DIR)
os.environ["DATURE_APP_ENV"] = "production"


@dataclass
class Config:
    host: str
    port: int


config = dature.load(
    dature.Yaml12Source(file="$DATURE_SOURCES_DIR/config.$DATURE_APP_ENV.yaml"),
    schema=Config,
)

assert config.host == "prod.example.com"
assert config.port == 443
# --8<-- [end:example]
