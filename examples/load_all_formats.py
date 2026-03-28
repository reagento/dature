"""dature.load() as a function — auto-detect format by file extension."""

from pathlib import Path

from all_types_dataclass import AllPythonTypesCompact  # type: ignore[import-not-found]

from dature import Source, load
from dature.sources_loader.docker_secrets import DockerSecretsLoader
from dature.sources_loader.toml_ import Toml10Loader
from dature.sources_loader.yaml_ import Yaml11Loader, Yaml12Loader

SOURCES_DIR = Path(__file__).parent / "sources"

FORMATS = {
    "json": Source(file=SOURCES_DIR / "all_types.json"),
    "json5": Source(file=SOURCES_DIR / "all_types.json5"),
    "toml10": Source(file=SOURCES_DIR / "all_types_toml10.toml", loader=Toml10Loader),
    "toml11": Source(file=SOURCES_DIR / "all_types_toml11.toml"),
    "ini": Source(file=SOURCES_DIR / "all_types.ini", prefix="all_types"),
    "yaml11": Source(file=SOURCES_DIR / "all_types_yaml11.yaml", loader=Yaml11Loader),
    "yaml12": Source(file=SOURCES_DIR / "all_types_yaml12.yaml", loader=Yaml12Loader),
    "env": Source(file=SOURCES_DIR / "all_types.env"),
    "docker_secrets": Source(
        file=SOURCES_DIR / "all_types_docker_secrets",
        loader=DockerSecretsLoader,
    ),
}

for meta in FORMATS.values():
    config = load(meta, AllPythonTypesCompact)
    assert config.string_value == "hello world"
    assert config.integer_value == 42
