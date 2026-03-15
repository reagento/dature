"""Heuristic masking — random tokens are masked in error messages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    connection_id: Literal["conn-1", "conn-2"]
    host: str


try:
    load(
        LoadMetadata(file_=SOURCES_DIR / "masking_heuristic.yaml", mask_secrets=True),
        Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "masking_heuristic.yaml")
    assert str(exc) == "Config loading errors (1)"
    assert len(exc.exceptions) == 1
    assert str(exc.exceptions[0]) == (
        "  [connection_id]  Invalid variant: 'aK*****T6'\n"
        f"   └── FILE '{source}', line 1\n"
        '       connection_id: "aK*****T6"'
    )
else:
    raise AssertionError("Expected DatureConfigError")
