"""field_mapping — multiple aliases for a single field."""

from dataclasses import dataclass

import dature


@dataclass
class Config:
    name: str


# --8<-- [start:aliases]
field_mapping = {dature.F[Config].name: ("fullName", "userName")}
# --8<-- [end:aliases]
