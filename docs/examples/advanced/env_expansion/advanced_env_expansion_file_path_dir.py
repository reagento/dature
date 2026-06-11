from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

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
# --8<-- [end:example]