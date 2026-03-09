"""dature.load() with explicit loader=IniLoader and prefix for section selection."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.sources_loader.ini_ import IniLoader

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class ServerConfig:
    host: str
    port: int
    debug: bool
    workers: int


config = load(
    LoadMetadata(file_=SOURCES_DIR / "server.ini", loader=IniLoader, prefix="server"),
    ServerConfig,
)

print(f"host: {config.host}")  # host: 0.0.0.0
print(f"port: {config.port}")  # port: 8080
print(f"debug: {config.debug}")  # debug: True
print(f"workers: {config.workers}")  # workers: 4
