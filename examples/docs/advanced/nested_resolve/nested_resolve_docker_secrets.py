"""nested_resolve_strategy with Docker secrets source."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from dature import Source, load
from dature.sources_loader.docker_secrets import DockerSecretsLoader


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database


with TemporaryDirectory() as secrets_dir:
    secrets_path = Path(secrets_dir)
    (secrets_path / "database").write_text('{"host": "json-host", "port": "5432"}')
    (secrets_path / "database__host").write_text("flat-host")
    (secrets_path / "database__port").write_text("3306")

    config = load(
        Source(
            file=secrets_path,
            loader=DockerSecretsLoader,
            nested_resolve_strategy="json",
        ),
        Config,
    )

    assert config.database.host == "json-host"
    assert config.database.port == 5432
