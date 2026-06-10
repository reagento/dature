# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    value: str = ""
# --8<-- [end:setup]

# --8<-- [start:example]
cfg = dature.load(
    dature.JsonSource(file=str(SOURCES_DIR / "$${@env.something}")),
    schema=Config,
)

assert cfg.value == "hello"

# --8<-- [end:example]
