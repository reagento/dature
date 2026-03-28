"""ENV expansion — variable in directory path."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import Source, load

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["DATURE_SOURCES_DIR"] = str(SOURCES_DIR)


@dataclass
class Config:
    host: str
    port: int


config = load(
    Source(file="$DATURE_SOURCES_DIR/advanced_env_expansion_file_path.yaml"),
    Config,
)

assert config.host == "localhost"
assert config.port == 8080
