"""Masking by name — secrets are masked in error messages."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
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
    assert str(exc) == dedent(f"""\
    Config loading errors (1)

      [password]  Invalid variant: 'my*****rd'
       └── FILE '{source}', line 1
           password: "my*****rd"
    """)
else:
    raise AssertionError("Expected DatureConfigError")
