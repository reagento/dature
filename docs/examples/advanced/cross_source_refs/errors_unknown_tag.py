# --8<-- [start:setup]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str = ""
    port: int = 8080


# --8<-- [end:setup]

# --8<-- [start:example]
dature.load(
    dature.EnvSource(),
    dature.JsonSource(file="${@vault.config_path}"),
    schema=Config,
)

# --8<-- [end:example]
