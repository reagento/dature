"""Metadata validators for nested dataclass fields."""

from dataclasses import dataclass

import dature
from dature import V


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database


# --8<-- [start:nested]
validators = {
    dature.F[Config].database.host: V.len() >= 1,
    dature.F[Config].database.port: V > 0,
}
# --8<-- [end:nested]
