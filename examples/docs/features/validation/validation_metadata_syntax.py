"""Metadata validators syntax — single validator vs tuple for multiple."""

from dataclasses import dataclass

import dature
from dature.validators.number import Gt, Lt
from dature.validators.string import MinLength


@dataclass
class Config:
    host: str
    port: int


# --8<-- [start:syntax]
validators = {
    dature.F[Config].port: (Gt(0), Lt(65536)),  # tuple for multiple
    dature.F[Config].host: MinLength(1),  # single, no tuple needed
}
# --8<-- [end:syntax]
