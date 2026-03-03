"""Load from INI file with section prefix."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(
    LoadMetadata(file_=str(SOURCES_DIR / "app.ini"), prefix="app"),
    Config,
)

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: False
