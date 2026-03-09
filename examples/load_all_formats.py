"""dature.load() as a function — auto-detect format by file extension."""

from pathlib import Path

from all_types_dataclass import AllPythonTypesCompact  # type: ignore[import-not-found]

from dature import LoadMetadata, load
from dature.sources_loader.docker_secrets import DockerSecretsLoader
from dature.sources_loader.toml_ import Toml10Loader
from dature.sources_loader.yaml_ import Yaml11Loader, Yaml12Loader

SOURCES_DIR = Path(__file__).parent / "sources"

FORMATS = {
    "json": LoadMetadata(file_=SOURCES_DIR / "all_types.json"),
    "json5": LoadMetadata(file_=SOURCES_DIR / "all_types.json5"),
    "toml10": LoadMetadata(file_=SOURCES_DIR / "all_types_toml10.toml", loader=Toml10Loader),
    "toml11": LoadMetadata(file_=SOURCES_DIR / "all_types_toml11.toml"),
    "ini": LoadMetadata(file_=SOURCES_DIR / "all_types.ini", prefix="all_types"),
    "yaml11": LoadMetadata(file_=SOURCES_DIR / "all_types_yaml11.yaml", loader=Yaml11Loader),
    "yaml12": LoadMetadata(file_=SOURCES_DIR / "all_types_yaml12.yaml", loader=Yaml12Loader),
    "env": LoadMetadata(file_=SOURCES_DIR / "all_types.env"),
    "docker_secrets": LoadMetadata(
        file_=SOURCES_DIR / "all_types_docker_secrets",
        loader=DockerSecretsLoader,
    ),
}

for name, meta in FORMATS.items():
    config = load(meta, AllPythonTypesCompact)
    print(f"[{name}] string_value={config.string_value}, integer_value={config.integer_value}")  # hello world, 42
    print(f"[{name}] string_value={config.string_value}, integer_value={config.integer_value}")  # hello world, 42
