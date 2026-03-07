"""Debug logging — all loading steps are logged at DEBUG level under the "dature" logger."""

import logging
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, load

logging.basicConfig(level=logging.DEBUG, format="%(message)s")

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    workers: int
    tags: list[str]


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=str(SOURCES_DIR / "defaults.yaml")),
            LoadMetadata(file_=str(SOURCES_DIR / "overrides.yaml")),
        ),
    ),
    Config,
)

# Output:
# [Config] Source 0 loaded: loader=yaml1.2, file=.../defaults.yaml, keys=['debug', 'host', 'port', 'tags', 'workers']
# [Config] Source 0 raw data: {'host': 'localhost', 'port': 3000, 'debug': False, 'workers': 1, 'tags': ['default']}
# [Config] Source 1 loaded: loader=yaml1.2, file=.../overrides.yaml, keys=['debug', 'host', 'port', 'tags', 'workers']
# [Config] Source 1 raw data: {'host': 'production.example.com', 'port': 8080, 'debug': True, 'workers': 4, 'tags': ['web', 'api']}
# [Config] Merge step 0 (strategy=last_wins): added=['debug', 'host', 'port', 'tags', 'workers'], overwritten=[]
# [Config] State after step 0: {'host': 'localhost', 'port': 3000, 'debug': False, 'workers': 1, 'tags': ['default']}
# [Config] Merge step 1 (strategy=last_wins): added=[], overwritten=['debug', 'host', 'port', 'tags', 'workers']
# [Config] State after step 1: {'host': 'production.example.com', 'port': 8080, 'debug': True, 'workers': 4, 'tags': ['web', 'api']}
# [Config] Merged result (strategy=last_wins, 2 sources): {'host': 'production.example.com', 'port': 8080, 'debug': True, 'workers': 4, 'tags': ['web', 'api']}
# [Config] Field 'debug' = True  <-- source 1 (.../overrides.yaml)
# [Config] Field 'host' = 'production.example.com'  <-- source 1 (.../overrides.yaml)
# [Config] Field 'port' = 8080  <-- source 1 (.../overrides.yaml)
# [Config] Field 'tags' = ['web', 'api']  <-- source 1 (.../overrides.yaml)
# [Config] Field 'workers' = 4  <-- source 1 (.../overrides.yaml)
