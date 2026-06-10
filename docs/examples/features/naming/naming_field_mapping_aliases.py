# --8<-- [start:setup]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    name: str
# --8<-- [end:setup]

# --8<-- [start:example]
field_mapping = {dature.F[Config].name: ("fullName", "userName")}
# --8<-- [end:example]
