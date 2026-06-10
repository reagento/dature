# --8<-- [start:setup]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str = ""


# --8<-- [end:setup]

# --8<-- [start:example]
dature.load(
    dature.EnvSource(prefix="${@json.prefix_key}"),
    dature.JsonSource(file="${@env.config_path}"),
    schema=Config,
)

# --8<-- [end:example]
