from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    value: str = ""

cfg = dature.load(
    dature.JsonSource(file=str(SOURCES_DIR / "$${@env.something}")),
    schema=Config,
)

assert cfg.value == "hello"