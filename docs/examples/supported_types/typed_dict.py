"""TypedDict example — used in docs/supported_types.md."""

from dataclasses import dataclass
from pathlib import Path

import dature
from typing_extensions import TypedDict


# --8<-- [start:schema]
class Credentials(TypedDict, extra_items=str):
    user: str
    password: str


@dataclass
class Config:
    name: str
    credentials: Credentials


EXPECTED_CONFIG = Config(
    name="app",
    credentials={
        "user": "admin",
        "password": "secret",
        "host": "localhost",
        "region": "eu",
    },  # type: ignore[typeddict-unknown-key]
)

SOURCES_DIR = Path(__file__).parent / "sources"

config = dature.load(
    dature.JsonSource(file=SOURCES_DIR / "typed_dict.json"), schema=Config
)

assert config == EXPECTED_CONFIG
# --8<-- [end:schema]
