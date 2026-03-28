"""dature vs Dynaconf — root validators for cross-field checks."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from dature import Source, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Gt, Lt
from dature.validators.root import RootValidator

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: Annotated[int, Gt(value=0), Lt(value=65536)]
    debug: bool = False


# --8<-- [start:root-validators]
def check_debug_port(config: Config) -> bool:
    return not (config.debug and config.port == 80)


try:
    load(
        Source(
            file=SOURCES_DIR / "dynaconf_root_validators_invalid.toml",
            root_validators=(
                RootValidator(
                    func=check_debug_port,
                    error_message="debug mode should not use port 80",
                ),
            ),
        ),
        Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "dynaconf_root_validators_invalid.toml")
    assert str(exc) == "Config loading errors (1)"
    # fmt: off
    assert str(exc.exceptions[0]) == (
        "  [<root>]  debug mode should not use port 80\n"
        f"   └── FILE '{source}'"
    )
    # fmt: on
else:
    raise AssertionError("Expected DatureConfigError")
# --8<-- [end:root-validators]
