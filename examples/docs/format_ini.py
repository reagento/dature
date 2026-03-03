"""Load from INI file with section prefix."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.sources_loader.ini_ import IniLoader

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(
    LoadMetadata(file_=str(SOURCES_DIR / "app.ini"), loader=IniLoader, prefix="app"),
    Config,
)

print(f"host: {config.host}")
print(f"port: {config.port}")
print(f"debug: {config.debug}")
