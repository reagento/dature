"""dature vs Hydra — multi-format merge with auto-detection."""

from dataclasses import dataclass
from pathlib import Path

from dature import Merge, Source, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


# --8<-- [start:merge]
config = load(
    Merge(
        Source(file_=SOURCES_DIR / "hydra_defaults.yaml"),
        Source(file_=SOURCES_DIR / "hydra_config.toml", skip_if_broken=True),
        Source(prefix="APP_"),
    ),
    Config,
)
# --8<-- [end:merge]

assert config.host == "localhost"
assert config.port == 9090
