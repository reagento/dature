"""dature vs pydantic-settings — real merge control."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


# --8<-- [start:merge]
config = dature.load(
    dature.Source(file=SOURCES_DIR / "pydantic_settings_merge_defaults.yaml"),
    dature.Source(file=SOURCES_DIR / "pydantic_settings_merge_local.yaml", skip_if_broken=True),
    dature.Source(prefix="APP_"),
    schema=Config,
)
# --8<-- [end:merge]

assert config.host == "localhost"
assert config.port == 9090
