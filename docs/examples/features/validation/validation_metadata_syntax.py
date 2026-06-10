# --8<-- [start:setup]
from dataclasses import dataclass

import dature
from dature import V


@dataclass
class Config:
    host: str
    port: int
# --8<-- [end:setup]

# --8<-- [start:example]
validators = {
    dature.F[Config].port: (V > 0) & (V < 65536),
    dature.F[Config].host: V.len() >= 1,
}

validators_tuple = {
    dature.F[Config].port: (V > 0, V < 65536),
}
# --8<-- [end:example]
