"""Custom type loader — teach dature to parse 'r,g,b' strings into an Rgb dataclass."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, TypeLoader, load

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


config = load(
    LoadMetadata(
        file_=SOURCES_DIR / "custom_type_common.yaml",
        type_loaders=(TypeLoader(type_=Rgb, func=rgb_from_string),),
    ),
    AppConfig,
)

assert config == AppConfig(name="my-app", color=Rgb(r=255, g=128, b=0))
