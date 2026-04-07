"""Multiple Annotated validators can be combined on a single field."""

from dataclasses import dataclass
from typing import Annotated

from dature.validators.number import Ge, Le
from dature.validators.sequence import MaxItems, MinItems, UniqueItems


@dataclass
class Config:
    # --8<-- [start:combined]
    port: Annotated[int, Ge(1), Le(65535)]
    tags: Annotated[list[str], MinItems(1), MaxItems(10), UniqueItems()]
    # --8<-- [end:combined]
