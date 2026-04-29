"""Multiple Annotated validators can be combined on a single field."""

from dataclasses import dataclass
from typing import Annotated

from dature import V


@dataclass
class Config:
    # --8<-- [start:combined]
    port: Annotated[int, (V >= 1) & (V <= 65535)]
    tags: Annotated[
        list[str],
        (V.len() >= 1) & (V.len() <= 10) & V.unique_items(),
    ]
    # --8<-- [end:combined]
