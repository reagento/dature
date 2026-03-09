"""Decorator mode — auto-load config from a YAML file."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@load(LoadMetadata(file_=SOURCES_DIR / "app.yaml"))
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = Config()  # type: ignore[call-arg]

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: False
