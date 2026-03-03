"""Load from all supported formats — JSON, JSON5, YAML, TOML, INI, ENV, Docker secrets."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.sources_loader.docker_secrets import DockerSecretsLoader
from dature.sources_loader.ini_ import IniLoader

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


formats = {
    "YAML": LoadMetadata(file_=str(SOURCES_DIR / "app.yaml")),
    "JSON": LoadMetadata(file_=str(SOURCES_DIR / "app.json")),
    "JSON5": LoadMetadata(file_=str(SOURCES_DIR / "app.json5")),
    "TOML": LoadMetadata(file_=str(SOURCES_DIR / "app.toml")),
    "INI": LoadMetadata(file_=str(SOURCES_DIR / "app.ini"), loader=IniLoader, prefix="app"),
    "ENV": LoadMetadata(file_=str(SOURCES_DIR / "app.env")),
    "Docker": LoadMetadata(file_=str(SOURCES_DIR / "app_docker_secrets"), loader=DockerSecretsLoader),
}

for name, meta in formats.items():
    config = load(meta, Config)
    print(f"[{name}] host={config.host}, port={config.port}, debug={config.debug}")
