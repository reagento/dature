"""skip_invalid_fields — drop invalid fields, let defaults fill in."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int = 3000
    debug: bool = False


config = load(
    LoadMetadata(file_=SOURCES_DIR / "merging_skip_invalid_defaults.yaml", skip_if_invalid=True),
    Config,
)

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 3000
print(f"debug: {config.debug}")  # debug: False
