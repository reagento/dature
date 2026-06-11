from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = dature.load(
    dature.JsonSource(file=SOURCES_DIR / "intro_app.json"),
    schema=Config,
)

# --8<-- [start:example-assertations]
assert config.host == "localhost"
assert config.port == 8080
assert config.debug is False
# --8<-- [end:example-assertations]
