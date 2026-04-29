"""Metadata validators syntax — single predicate vs tuple vs `&` composition."""

from dataclasses import dataclass

import dature
from dature import V


@dataclass
class Config:
    host: str
    port: int


# --8<-- [start:syntax]
validators = {
    dature.F[Config].port: (V > 0) & (V < 65536),  # composed with & (preferred)
    dature.F[Config].host: V.len() >= 1,  # single predicate
}

# alternative: tuple of predicates — equivalent to &
validators_tuple = {
    dature.F[Config].port: (V > 0, V < 65536),
}
# --8<-- [end:syntax]
