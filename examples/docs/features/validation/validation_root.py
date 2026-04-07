"""Root validator — error example."""

from dataclasses import dataclass
from pathlib import Path

import dature
from dature.validators.root import RootValidator

SOURCES_DIR = Path(__file__).parent / "sources"


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
            RootValidator(
                func=check_debug_not_on_production,
                error_message="debug=True is not allowed on non-localhost hosts",
            ),
        ),
    ),
    schema=Config,
)
