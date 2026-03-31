"""Global type_loaders via dature.configure() — register custom type parsers for all load() calls."""

from dataclasses import dataclass
from pathlib import Path

import dature

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
dature.configure(type_loaders={Rgb: rgb_from_string})

config = dature.load(dature.Source(file=SOURCES_DIR / "custom_type_common.yaml"), schema=AppConfig)
assert config == AppConfig(name="my-app", color=Rgb(r=255, g=128, b=0))
