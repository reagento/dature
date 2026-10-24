from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

os.environ["KNOWN_HOST"] = "https://api.example.com"


@dataclass
class Config:
    set_url: str
    unset_url: str


config = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "advanced_env_expansion_merge.yaml",
        expand_env_vars="empty",
    ),
    schema=Config,
)

assert config.set_url == "https://api.example.com/api"
assert config.unset_url == "/api"
# --8<-- [end:example]
