"""Global type_loaders via configure() — register custom type parsers for all load() calls."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, TypeLoader, configure, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass(frozen=True, slots=True)
class Rgb:
    r: int
    g: int
    b: int


def rgb_from_string(value: str) -> Rgb:
    parts = value.split(",")
    return Rgb(r=int(parts[0]), g=int(parts[1]), b=int(parts[2]))


@dataclass
class AppConfig:
    name: str
    color: Rgb


# Register Rgb parser globally — no need to pass type_loaders to every load() call
configure(type_loaders=(TypeLoader(type_=Rgb, func=rgb_from_string),))

config = load(LoadMetadata(file_=SOURCES_DIR / "custom_type_common.yaml"), AppConfig)
assert config == AppConfig(name="my-app", color=Rgb(r=255, g=128, b=0))
