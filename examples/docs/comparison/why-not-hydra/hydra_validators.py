"""dature vs Hydra — Annotated validators for value constraints."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Gt, Lt

SOURCES_DIR = Path(__file__).parent / "sources"


# --8<-- [start:validators]
@dataclass
class Config:
    host: str
    port: Annotated[int, Gt(value=0), Lt(value=65536)] = 8080


try:
    dature.load(dature.Source(file=SOURCES_DIR / "hydra_validators_invalid.yaml"), dataclass_=Config)
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "hydra_validators_invalid.yaml")
    assert str(exc) == "Config loading errors (1)"
    # fmt: off
    assert str(exc.exceptions[0]) == (
        "  [port]  Value must be greater than 0\n"
        "   ├── port: -1\n"
        "   │         ^^\n"
        f"   └── FILE '{source}', line 2"
    )
    # fmt: on
else:
    raise AssertionError("Expected DatureConfigError")
# --8<-- [end:validators]
