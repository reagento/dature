"""Cross-source references — $$ escaping in init-fields."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    value: str = ""


# SOURCES_DIR contains a file literally named "${@env.something}".
# $${@env.something} in the file= argument escapes to "${@env.something}",
# so dature opens the file by that exact name instead of treating it as a ref.
cfg = dature.load(
    dature.JsonSource(file=str(SOURCES_DIR / "$${@env.something}")),
    schema=Config,
)

assert cfg.value == "hello"
