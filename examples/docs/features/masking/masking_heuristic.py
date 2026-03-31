"""Heuristic masking — random tokens are masked in error messages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import dature
from dature.errors import DatureConfigError

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    connection_id: Literal["conn-1", "conn-2"]
    host: str


try:
    dature.load(
        dature.Source(file=SOURCES_DIR / "masking_heuristic.yaml", mask_secrets=True),
        dataclass_=Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "masking_heuristic.yaml")
    assert str(exc) == "Config loading errors (1)"
    assert len(exc.exceptions) == 1
    assert str(exc.exceptions[0]) == (
        "  [connection_id]  Invalid variant: '<REDACTED>'\n"
        '   ├── connection_id: "<REDACTED>"\n'
        "   │                   ^^^^^^^^^^\n"
        f"   └── FILE '{source}', line 1"
    )
else:
    raise AssertionError("Expected DatureConfigError")
