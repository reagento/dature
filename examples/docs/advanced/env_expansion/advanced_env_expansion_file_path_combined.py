"""ENV expansion — variables in both directory path and file name."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import Source, load

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["DATURE_SOURCES_DIR"] = str(SOURCES_DIR)
os.environ["DATURE_APP_ENV"] = "production"


@dataclass
class Config:
    host: str
    port: int


config = load(
    Source(file_="$DATURE_SOURCES_DIR/config.$DATURE_APP_ENV.yaml"),
    Config,
)

assert config.host == "prod.example.com"
assert config.port == 443
