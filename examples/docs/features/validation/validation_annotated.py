"""Annotated validators — error example."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Annotated

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Ge, Le
from dature.validators.sequence import MinItems, UniqueItems
from dature.validators.string import MaxLength, MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class ServiceConfig:
    port: Annotated[int, Ge(value=1), Le(value=65535)]
    name: Annotated[str, MinLength(value=3), MaxLength(value=50)]
    tags: Annotated[list[str], MinItems(value=1), UniqueItems()]
    workers: Annotated[int, Ge(value=1)]


try:
    load(
        LoadMetadata(file_=SOURCES_DIR / "validation_annotated_invalid.json5"),
        ServiceConfig,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "validation_annotated_invalid.json5")
    assert str(exc) == dedent(f"""\
        ServiceConfig loading errors (4)

          [port]  Value must be greater than or equal to 1
           └── FILE '{source}', line 3
               port: 0,

          [name]  Value must have at least 3 characters
           └── FILE '{source}', line 4
               name: "ab",

          [tags]  Value must contain unique items
           └── FILE '{source}', line 5
               tags: ["web", "web"],

          [workers]  Value must be greater than or equal to 1
           └── FILE '{source}', line 6
               workers: 0,
        """)
