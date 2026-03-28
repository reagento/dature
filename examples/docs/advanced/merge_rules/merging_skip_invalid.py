"""skip_invalid_fields — drop invalid fields, let defaults fill in."""

from dataclasses import dataclass
from pathlib import Path

from dature import Source, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int = 3000


config = load(
    Source(file=SOURCES_DIR / "merging_skip_invalid_defaults.yaml", skip_if_invalid=True),
    Config,
)

assert config.host == "localhost"
assert config.port == 3000
