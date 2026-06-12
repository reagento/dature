from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature
from dature import V


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


def check_debug_not_on_production(obj: Config) -> bool:
    if obj.host != "localhost" and obj.debug:
        return False
    return True

dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "validation_root_invalid.yaml",
        root_validators=(
            V.root(
                check_debug_not_on_production,
                error_message=(
                    "debug=True is not allowed on non-localhost hosts"
                ),
            ),
        ),
    ),
    schema=Config,
)
# --8<-- [end:example]
