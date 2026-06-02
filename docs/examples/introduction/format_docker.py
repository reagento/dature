"""Load from Docker secrets directory."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = dature.load(
    dature.DockerSecretsSource(dir_=SOURCES_DIR / "intro_app_docker_secrets"),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
