"""Debug logging — all loading steps are logged at DEBUG level under the "dature" logger."""

import io
import logging
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, load

log_stream = io.StringIO()
handler = logging.StreamHandler(log_stream)
handler.setLevel(logging.DEBUG)
logging.getLogger("dature").addHandler(handler)
logging.getLogger("dature").setLevel(logging.DEBUG)

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),
            LoadMetadata(file_=SHARED_DIR / "common_overrides.yaml"),
        ),
    ),
    Config,
)

log_lines = [line for line in log_stream.getvalue().splitlines() if "[Config]" in line]

defaults = str(SHARED_DIR / "common_defaults.yaml")
overrides = str(SHARED_DIR / "common_overrides.yaml")

assert log_lines == [
    f"[Config] Source 0 loaded: loader=yaml1.2, file={defaults}, keys=['host', 'port', 'tags']",
    "[Config] Source 0 raw data: {'host': 'localhost', 'port': 3000, 'tags': ['default']}",
    f"[Config] Source 1 loaded: loader=yaml1.2, file={overrides}, keys=['host', 'port', 'tags']",
    "[Config] Source 1 raw data: {'host': 'production.example.com', 'port': 8080, 'tags': ['web', 'api']}",
    "[Config] Merge step 0 (strategy=last_wins): added=['host', 'port', 'tags'], overwritten=[]",
    "[Config] State after step 0: {'host': 'localhost', 'port': 3000, 'tags': ['default']}",
    "[Config] Merge step 1 (strategy=last_wins): added=[], overwritten=['host', 'port', 'tags']",
    "[Config] State after step 1: {'host': 'production.example.com', 'port': 8080, 'tags': ['web', 'api']}",
    "[Config] Merged result (strategy=last_wins, 2 sources): {'host': 'production.example.com', 'port': 8080, 'tags': ['web', 'api']}",
    f"[Config] Field 'host' = 'production.example.com'  <-- source 1 ({overrides})",
    f"[Config] Field 'port' = 8080  <-- source 1 ({overrides})",
    f"[Config] Field 'tags' = ['web', 'api']  <-- source 1 ({overrides})",
]
