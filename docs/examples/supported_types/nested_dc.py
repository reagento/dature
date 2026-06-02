"""Nested dataclasses example — used in docs/supported_types.md."""

from dataclasses import dataclass
from pathlib import Path

import dature


# --8<-- [start:schema]
@dataclass
class Address:
    city: str
    zip_code: str


@dataclass
class Tag:
    name: str
    priority: int


@dataclass
class Config:
    address: Address
    tags: list[Tag]
    addrs: dict[str, Address]


EXPECTED_CONFIG = Config(
    address=Address(city="Moscow", zip_code="101000"),
    tags=[
        Tag(name="urgent", priority=1),
        Tag(name="low", priority=5),
    ],
    addrs={
        "home": Address(city="Berlin", zip_code="10115"),
        "work": Address(city="Paris", zip_code="75001"),
    },
)
# --8<-- [end:schema]


SOURCES_DIR = Path(__file__).parent / "sources"

FORMATS = {
    "yaml12": dature.Yaml12Source(file=SOURCES_DIR / "nested_dc.yaml"),
    "json": dature.JsonSource(file=SOURCES_DIR / "nested_dc.json"),
    "json5": dature.Json5Source(file=SOURCES_DIR / "nested_dc.json5"),
    "toml11": dature.Toml11Source(file=SOURCES_DIR / "nested_dc.toml"),
    "ini": dature.IniSource(
        file=SOURCES_DIR / "nested_dc.ini",
        prefix="nested_dc",
    ),
    "envfile": dature.EnvFileSource(file=SOURCES_DIR / "nested_dc.env"),
    "docker_secrets": dature.DockerSecretsSource(
        dir_=SOURCES_DIR / "nested_dc_docker_secrets",
    ),
}

for src in FORMATS.values():
    config = dature.load(src, schema=Config)
    assert config == EXPECTED_CONFIG
