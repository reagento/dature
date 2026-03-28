"""dature vs Dynaconf — explicit merge strategies in code."""

from dataclasses import dataclass
from pathlib import Path

from dature import Merge, MergeStrategy, Source, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


# --8<-- [start:merge]
config = load(
    Merge(
        Source(file=SOURCES_DIR / "dynaconf_merge_defaults.yaml"),
        Source(file=SOURCES_DIR / "dynaconf_merge_local.yaml", skip_if_broken=True),
        strategy=MergeStrategy.LAST_WINS,
    ),
    Config,
)
# --8<-- [end:merge]

assert config.host == "localhost"
assert config.port == 9090
