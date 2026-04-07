"""Metadata validators for nested dataclass fields."""

from dataclasses import dataclass

import dature
from dature.validators.number import Gt
from dature.validators.string import MinLength


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database


# --8<-- [start:nested]
validators = {
    dature.F[Config].database.host: MinLength(1),
    dature.F[Config].database.port: Gt(0),
}
# --8<-- [end:nested]
