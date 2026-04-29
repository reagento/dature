"""ENV expansion — merge mode with per-source override."""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

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


config = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "advanced_env_expansion_merge_default.yaml",
    ),  # uses global "default"
    dature.Yaml12Source(
        file=SOURCES_DIR / "advanced_env_expansion_merge_empty.yaml",
        expand_env_vars="empty",
    ),
    dature.Yaml12Source(
        file=SOURCES_DIR / "advanced_env_expansion_merge_disabled.yaml",
        expand_env_vars="disabled",
    ),
    schema=Config,
    expand_env_vars="default",  # global default for all sources
)

assert config.default_set_url == "https://api.example.com/api"
assert config.default_unset_url == "$UNSET_VAR/api"
assert config.empty_set_url == "https://api.example.com/api"
assert config.empty_unset_url == "/api"
assert config.disabled_set_url == "$KNOWN_HOST/api"
assert config.disabled_unset_url == "$UNSET_VAR/api"
