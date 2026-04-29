"""Debug logging — loading steps are logged at DEBUG under "dature"."""

import io
import logging
from dataclasses import dataclass
from pathlib import Path

import dature

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


config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Yaml12Source(file=SHARED_DIR / "common_overrides.yaml"),
    schema=Config,
)

log_lines = [
    line for line in log_stream.getvalue().splitlines() if "[Config]" in line
]

defaults = str(SHARED_DIR / "common_defaults.yaml")
overrides = str(SHARED_DIR / "common_overrides.yaml")

keys = "['host', 'port', 'tags']"
defaults_data = "{'host': 'localhost', 'port': 3000, 'tags': ['default']}"
overrides_data = (
    "{'host': 'production.example.com', 'port': 8080, 'tags': ['web', 'api']}"
)
assert log_lines == [
    f"[Config] Source 0 loaded: loader=yaml1.2, file={defaults}, keys={keys}",
    f"[Config] Source 0 raw data: {defaults_data}",
    (
        "[Config] Merge step 0 (strategy=last_wins): "
        "added=['host', 'port', 'tags'], overwritten=[]"
    ),
    f"[Config] State after step 0: {defaults_data}",
    f"[Config] Source 1 loaded: loader=yaml1.2, file={overrides}, keys={keys}",
    f"[Config] Source 1 raw data: {overrides_data}",
    (
        "[Config] Merge step 1 (strategy=last_wins): "
        "added=[], overwritten=['host', 'port', 'tags']"
    ),
    f"[Config] State after step 1: {overrides_data}",
    (
        "[Config] Merged result (strategy=last_wins, 2 sources): "
        f"{overrides_data}"
    ),
    f"[Config] Field 'host' = 'production.example.com'"
    f"  <-- source 1 ({overrides})",
    f"[Config] Field 'port' = 8080  <-- source 1 ({overrides})",
    f"[Config] Field 'tags' = ['web', 'api']  <-- source 1 ({overrides})",
]
