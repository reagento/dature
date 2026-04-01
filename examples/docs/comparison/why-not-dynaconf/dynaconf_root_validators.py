"""dature vs Dynaconf — root validators for cross-field checks."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature.validators.number import Gt, Lt
from dature.validators.root import RootValidator

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: Annotated[int, Gt(0), Lt(65536)]
    debug: bool = False


def check_debug_port(config: Config) -> bool:
    return not (config.debug and config.port == 80)


dature.load(
    dature.Source(
        file=SOURCES_DIR / "dynaconf_root_validators_invalid.toml",
        root_validators=(
            RootValidator(
                check_debug_port,
                error_message="debug mode should not use port 80",
            ),
        ),
    ),
    schema=Config,
)
