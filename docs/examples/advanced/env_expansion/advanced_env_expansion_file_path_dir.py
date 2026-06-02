"""ENV expansion — variable in directory path."""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["DATURE_SOURCES_DIR"] = str(SOURCES_DIR)


@dataclass
class Config:
    host: str
    port: int


config = dature.load(
    dature.Yaml12Source(
        file="$DATURE_SOURCES_DIR/advanced_env_expansion_file_path.yaml",
    ),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 8080
