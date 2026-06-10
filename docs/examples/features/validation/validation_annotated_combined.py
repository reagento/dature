# --8<-- [start:setup]
from dataclasses import dataclass
from typing import Annotated

from dature import V
# --8<-- [end:setup]

# --8<-- [start:example]
@dataclass
class Config:
    port: Annotated[int, (V >= 1) & (V <= 65535)]
    tags: Annotated[
        list[str],
        (V.len() >= 1) & (V.len() <= 10) & V.unique_items(),
    ]
# --8<-- [end:example]
