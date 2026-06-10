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


# --8<-- [start:example]
path_eager = dature.F[Config].host
path_nested = dature.F[Config].database.host
path_string = dature.F["Config"].host
# --8<-- [end:example]
