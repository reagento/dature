# --8<-- [start:setup]
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


# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "custom_type_common.yaml"),
    dature.Yaml12Source(file=SOURCES_DIR / "custom_type_merge_override.yaml"),
    schema=AppConfig,
    type_loaders={Rgb: rgb_from_string},  # applies to all sources within a single load() call
)

assert config == AppConfig(name="my-app", color=Rgb(r=100, g=200, b=50))

# --8<-- [end:example]
