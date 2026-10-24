"""TypedDict(closed=True) example — used in docs/supported_types.md."""

from dataclasses import dataclass
from pathlib import Path

import dature
from typing_extensions import TypedDict


# --8<-- [start:schema]
class Credentials(TypedDict, closed=True):
    user: str
    password: str


@dataclass
class Config:
    name: str
    credentials: Credentials


SOURCES_DIR = Path(__file__).parent / "sources"

dature.load(
    dature.JsonSource(file=SOURCES_DIR / "typed_dict.json"), schema=Config
)
# --8<-- [end:schema]
