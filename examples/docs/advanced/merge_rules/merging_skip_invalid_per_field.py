"""skip_if_invalid per field — restrict skipping to specific fields."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, LoadMetadata, MergeMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    timeout: int


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SOURCES_DIR / "merging_skip_invalid_per_field_defaults.yaml"),
            LoadMetadata(
                file_=SOURCES_DIR / "merging_skip_invalid_per_field_overrides.yaml",
                skip_if_invalid=(F[Config].port, F[Config].timeout),
            ),
        ),
    ),
    Config,
)

assert config.host == "production.example.com"
assert config.port == 3000
assert config.timeout == 30
