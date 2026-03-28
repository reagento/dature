"""dature.load() as a function — auto-detect format by file extension."""

from pathlib import Path

from all_types_dataclass import AllPythonTypesCompact  # type: ignore[import-not-found]

import dature
from dature.sources_loader.docker_secrets import DockerSecretsLoader
from dature.sources_loader.toml_ import Toml10Loader
from dature.sources_loader.yaml_ import Yaml11Loader, Yaml12Loader

SOURCES_DIR = Path(__file__).parent / "sources"

FORMATS = {
    "json": dature.Source(file=SOURCES_DIR / "all_types.json"),
    "json5": dature.Source(file=SOURCES_DIR / "all_types.json5"),
    "toml10": dature.Source(file=SOURCES_DIR / "all_types_toml10.toml", loader=Toml10Loader),
    "toml11": dature.Source(file=SOURCES_DIR / "all_types_toml11.toml"),
    "ini": dature.Source(file=SOURCES_DIR / "all_types.ini", prefix="all_types"),
    "yaml11": dature.Source(file=SOURCES_DIR / "all_types_yaml11.yaml", loader=Yaml11Loader),
    "yaml12": dature.Source(file=SOURCES_DIR / "all_types_yaml12.yaml", loader=Yaml12Loader),
    "env": dature.Source(file=SOURCES_DIR / "all_types.env"),
    "docker_secrets": dature.Source(
        file=SOURCES_DIR / "all_types_docker_secrets",
        loader=DockerSecretsLoader,
    ),
}

for meta in FORMATS.values():
    config = dature.load(meta, dataclass_=AllPythonTypesCompact)
    assert config.string_value == "hello world"
    assert config.integer_value == 42
