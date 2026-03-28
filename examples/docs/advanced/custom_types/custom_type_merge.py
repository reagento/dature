"""Per-merge type_loaders — set type_loaders on Merge for multi-source loads."""

from dataclasses import dataclass
from pathlib import Path

from dature import Merge, Source, TypeLoader, load

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
    Merge(
        Source(file=SOURCES_DIR / "custom_type_common.yaml"),
        Source(file=SOURCES_DIR / "custom_type_merge_override.yaml"),
        type_loaders=(TypeLoader(type_=Rgb, func=rgb_from_string),),
    ),
    AppConfig,
)

assert config == AppConfig(name="my-app", color=Rgb(r=100, g=200, b=50))
