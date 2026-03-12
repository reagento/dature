"""ENV expansion — merge mode with per-source override."""

import os
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["KNOWN_HOST"] = "https://api.example.com"


@dataclass
class Config:
    default_set_url: str
    default_unset_url: str
    empty_set_url: str
    empty_unset_url: str
    disabled_set_url: str
    disabled_unset_url: str


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SOURCES_DIR / "advanced_env_expansion_merge_default.yaml"),  # uses global "default"
            LoadMetadata(file_=SOURCES_DIR / "advanced_env_expansion_merge_empty.yaml", expand_env_vars="empty"),
            LoadMetadata(file_=SOURCES_DIR / "advanced_env_expansion_merge_disabled.yaml", expand_env_vars="disabled"),
        ),
        expand_env_vars="default",  # global default for all sources
    ),
    Config,
)

print(f"default_set_url: {config.default_set_url}")  # default_set_url: https://api.example.com/api
print(f"default_unset_url: {config.default_unset_url}")  # default_unset_url: $UNSET_VAR/api
print(f"empty_set_url: {config.empty_set_url}")  # empty_set_url: https://api.example.com/api
print(f"empty_unset_url: {config.empty_unset_url}")  # empty_unset_url: /api
print(f"disabled_set_url: {config.disabled_set_url}")  # disabled_set_url: $KNOWN_HOST/api
print(f"disabled_unset_url: {config.disabled_unset_url}")  # disabled_unset_url: $UNSET_VAR/api
