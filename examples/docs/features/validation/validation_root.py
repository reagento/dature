"""Root validator — error example."""

from dataclasses import dataclass
from pathlib import Path

import dature
from dature.errors import DatureConfigError
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


try:
    dature.load(
        dature.Source(
            file=SOURCES_DIR / "validation_root_invalid.yaml",
            root_validators=(
                RootValidator(
                    func=check_debug_not_on_production,
                    error_message="debug=True is not allowed on non-localhost hosts",
                ),
            ),
        ),
        dataclass_=Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "validation_root_invalid.yaml")
    assert str(exc) == "Config loading errors (1)"
    assert len(exc.exceptions) == 1
    assert str(exc.exceptions[0]) == (
        f"  [<root>]  debug=True is not allowed on non-localhost hosts\n   └── FILE '{source}'"
    )
