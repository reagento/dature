"""Annotated validators — error example."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Ge, Le
from dature.validators.sequence import MinItems, UniqueItems
from dature.validators.string import MaxLength, MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class ServiceConfig:
    port: Annotated[int, Ge(1), Le(65535)]
    name: Annotated[str, MinLength(3), MaxLength(50)]
    tags: Annotated[list[str], MinItems(1), UniqueItems()]
    workers: Annotated[int, Ge(1)]


try:
    dature.load(
        dature.Source(file=SOURCES_DIR / "validation_annotated_invalid.json5"),
        dataclass_=ServiceConfig,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "validation_annotated_invalid.json5")
    assert str(exc) == "ServiceConfig loading errors (4)"
    assert len(exc.exceptions) == 4
    assert str(exc.exceptions[0]) == (
        f"  [port]  Value must be greater than or equal to 1\n"
        f"   ├── port: 0,\n"
        f"   │         ^\n"
        f"   └── FILE '{source}', line 3"
    )
    assert str(exc.exceptions[1]) == (
        f"  [name]  Value must have at least 3 characters\n"
        f'   ├── name: "ab",\n'
        f"   │          ^^\n"
        f"   └── FILE '{source}', line 4"
    )
    assert str(exc.exceptions[2]) == (
        f"  [tags]  Value must contain unique items\n"
        f'   ├── tags: ["web", "web"],\n'
        f"   │         ^^^^^^^^^^^^^^\n"
        f"   └── FILE '{source}', line 5"
    )
    assert str(exc.exceptions[3]) == (
        f"  [workers]  Value must be greater than or equal to 1\n"
        f"   ├── workers: 0,\n"
        f"   │            ^\n"
        f"   └── FILE '{source}', line 6"
    )
