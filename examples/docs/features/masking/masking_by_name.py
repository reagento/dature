"""Masking by name — auto-detect secrets by field name patterns."""

import io
import logging
from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

log_stream = io.StringIO()
handler = logging.StreamHandler(log_stream)
handler.setLevel(logging.DEBUG)
logging.getLogger("dature").addHandler(handler)
logging.getLogger("dature").setLevel(logging.DEBUG)

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    password: str
    api_key: str
    host: str


config = load(
    LoadMetadata(file_=SOURCES_DIR / "masking_by_name.yaml", mask_secrets=True),
    Config,
    debug=True,
)

assert config.host == "production"
assert config.password == "my_secret_password"
assert config.api_key == "sk-proj-abc123def456"

logs = log_stream.getvalue()
assert "'password': 'my*****rd'" in logs
assert "'api_key': 'sk*****56'" in logs
assert "'host': 'production'" in logs
