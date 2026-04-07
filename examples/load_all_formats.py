"""dature.load() as a function — load from every supported format."""

from pathlib import Path

from all_types_dataclass import AllPythonTypesCompact  # type: ignore[import-not-found]

import dature

SOURCES_DIR = Path(__file__).parent / "sources"

FORMATS = {
    "json": dature.JsonSource(file=SOURCES_DIR / "all_types.json"),
    "json5": dature.Json5Source(file=SOURCES_DIR / "all_types.json5"),
    "toml10": dature.Toml10Source(file=SOURCES_DIR / "all_types_toml10.toml"),
    "toml11": dature.Toml11Source(file=SOURCES_DIR / "all_types_toml11.toml"),
    "ini": dature.IniSource(file=SOURCES_DIR / "all_types.ini", prefix="all_types"),
    "yaml11": dature.Yaml11Source(file=SOURCES_DIR / "all_types_yaml11.yaml"),
    "yaml12": dature.Yaml12Source(file=SOURCES_DIR / "all_types_yaml12.yaml"),
    "env": dature.EnvFileSource(file=SOURCES_DIR / "all_types.env"),
    "docker_secrets": dature.DockerSecretsSource(
        dir_=SOURCES_DIR / "all_types_docker_secrets",
    ),
}

for meta in FORMATS.values():
    config = dature.load(meta, schema=AllPythonTypesCompact)
    assert config.string_value == "hello world"
    assert config.integer_value == 42
