"""skip_if_broken per source — override the global flag per LoadMetadata."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"
SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),  # uses global
            LoadMetadata(
                file_=SOURCES_DIR / "optional.yaml",
                skip_if_broken=True,
            ),  # always skip if broken
            LoadMetadata(
                file_=SHARED_DIR / "common_overrides.yaml",
                skip_if_broken=False,
            ),  # never skip, even if global is True
        ),
        skip_broken_sources=True,  # global default
    ),
    Config,
)

assert config.host == "production.example.com"
assert config.port == 8080
