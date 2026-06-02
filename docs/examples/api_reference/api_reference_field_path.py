"""F[] factory for building field paths with validation."""

from dataclasses import dataclass

import dature


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    database: Database
    host: str


path_eager = dature.F[Config].host
path_nested = dature.F[Config].database.host
path_string = dature.F["Config"].host
