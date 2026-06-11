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

validators = {
    dature.F[Config].database.host: V.len() >= 1,
    dature.F[Config].database.port: V > 0,
}
