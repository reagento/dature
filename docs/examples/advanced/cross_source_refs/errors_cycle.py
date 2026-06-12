from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str = ""


dature.load(
    dature.EnvSource(prefix="${@json.prefix_key}"),
    dature.JsonSource(file="${@env.config_path}"),
    schema=Config,
)
