# --8<-- [start:setup]
from dataclasses import dataclass
from typing import Annotated

import dature
from dature import V


@dataclass
class Config:
    port: Annotated[int, V >= 1]
# --8<-- [end:setup]

# --8<-- [start:example]
dature.load(
    dature.EnvSource(prefix="ERROR_FORMAT_"),
    schema=Config,
)
# --8<-- [end:example]
