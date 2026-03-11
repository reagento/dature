"""skip_if_broken per source — override the global flag per LoadMetadata."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SOURCES_DIR / "common_defaults.yaml"),  # uses global
            LoadMetadata(
                file_=SOURCES_DIR / "optional.yaml",
                skip_if_broken=True,
            ),  # always skip if broken
            LoadMetadata(
                file_=SOURCES_DIR / "common_overrides.yaml",
                skip_if_broken=False,
            ),  # never skip, even if global is True
        ),
        skip_broken_sources=True,  # global default
    ),
    Config,
)

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 3000
print(f"debug: {config.debug}")  # debug: False
