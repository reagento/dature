"""Masking by name — secrets are masked in error messages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    password: Literal["admin", "root"]
    host: str


try:
    load(LoadMetadata(file_=SOURCES_DIR / "masking_by_name.yaml"), Config)
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "masking_by_name.yaml")
    assert str(exc) == "Config loading errors (1)"
    assert len(exc.exceptions) == 1
    assert str(exc.exceptions[0]) == (
        f"  [password]  Invalid variant: 'my*****rd'\n   └── FILE '{source}', line 1\n       password: \"my*****rd\""
    )
else:
    raise AssertionError("Expected DatureConfigError")
