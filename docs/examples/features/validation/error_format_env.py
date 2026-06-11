# --8<-- [start:setup]
import os
from dataclasses import dataclass
from typing import Annotated

import dature
from dature import V

os.environ["APP_PORT"] = "0"


@dataclass
class Config:
    port: Annotated[int, V >= 1]
# --8<-- [end:setup]

# --8<-- [start:example]
dature.load(
    dature.EnvSource(prefix="APP_"),
    schema=Config,
)
# --8<-- [end:example]
