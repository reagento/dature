# --8<-- [start:setup]
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
# --8<-- [end:setup]

# --8<-- [start:example]
validators = {
    dature.F[Config].database.host: V.len() >= 1,
    dature.F[Config].database.port: V > 0,
}
# --8<-- [end:example]
