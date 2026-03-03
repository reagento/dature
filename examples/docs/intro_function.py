"""Function mode — load config from a YAML file."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(LoadMetadata(file_=str(SOURCES_DIR / "app.yaml")), Config)

print(f"host: {config.host}")
print(f"port: {config.port}")
print(f"debug: {config.debug}")
