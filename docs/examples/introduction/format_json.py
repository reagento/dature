from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = dature.load(
    dature.JsonSource(file=SOURCES_DIR / "intro_app.json"),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
# --8<-- [end:example]
