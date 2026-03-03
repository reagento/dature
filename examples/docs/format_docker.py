"""Load from Docker secrets directory."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.sources_loader.docker_secrets import DockerSecretsLoader

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(
    LoadMetadata(file_=str(SOURCES_DIR / "app_docker_secrets"), loader=DockerSecretsLoader),
    Config,
)

print(f"host: {config.host}")
print(f"port: {config.port}")
print(f"debug: {config.debug}")
