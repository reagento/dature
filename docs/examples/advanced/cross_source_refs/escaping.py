from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    value: str = ""

cfg = dature.load(
    dature.JsonSource(file=str(SOURCES_DIR / "$${@env.something}")),
    schema=Config,
)

assert cfg.value == "hello"
# --8<-- [end:example]
