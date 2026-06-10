# --8<-- [start:setup]
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
# --8<-- [end:setup]

# --8<-- [start:example]
dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "error_format_dataclass.yaml"),
    schema=Config,
)
# --8<-- [end:example]
