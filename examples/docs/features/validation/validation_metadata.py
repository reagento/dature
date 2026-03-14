"""Metadata validators — error example."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from dature import F, LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Ge, Lt
from dature.validators.string import MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


try:
    load(
        LoadMetadata(
            file_=SOURCES_DIR / "validation_metadata_invalid.yaml",
            validators={
                F[Config].host: MinLength(value=1),
                F[Config].port: (Ge(value=1), Lt(value=65536)),
            },
        ),
        Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "validation_metadata_invalid.yaml")
    assert str(exc) == dedent(f"""\
        Config loading errors (2)

          [host]  Value must have at least 1 characters
           └── FILE '{source}', line 1
               host: ""

          [port]  Value must be greater than or equal to 1
           └── FILE '{source}', line 2
               port: 0
        """)
