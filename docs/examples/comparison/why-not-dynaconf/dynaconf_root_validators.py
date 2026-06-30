from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass
from typing import Annotated

import dature
from dature import V


@dataclass
class Config:
    host: str
    port: Annotated[int, (V > 0) & (V < 65536)]
    debug: bool = False


def check_debug_port(config: Config) -> bool:
    return not (config.debug and config.port == 80)


dature.load(
    dature.Toml11Source(
        file=SOURCES_DIR / "dynaconf_root_validators_invalid.toml",
    ),
    schema=Config,
    root_validators=(
        V.root(
            check_debug_port,
            error_message="debug mode should not use port 80",
        ),
    ),
)
# --8<-- [end:example]
