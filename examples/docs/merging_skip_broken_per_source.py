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
            LoadMetadata(file_=str(SOURCES_DIR / "defaults.yaml")),  # uses global
            LoadMetadata(
                file_=str(SOURCES_DIR / "optional.yaml"),
                skip_if_broken=True,
            ),  # always skip if broken
            LoadMetadata(prefix="APP_", skip_if_broken=False),  # never skip
        ),
        skip_broken_sources=True,  # global default
    ),
    Config,
)

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 3000
print(f"debug: {config.debug}")  # debug: False
