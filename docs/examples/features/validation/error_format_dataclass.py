"""Error format — custom validator on a dataclass-typed field."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature import V

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Endpoint:
    host: str
    port: int


@dataclass
class Config:
    endpoint: Annotated[
        Endpoint,
        V.check(
            lambda ep: bool(ep.host),
            error_message="Endpoint host must not be empty",
        ),
    ]


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "error_format_dataclass.yaml"),
    schema=Config,
)
