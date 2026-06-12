from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str = ""
    port: int = 8080


dature.load(
    dature.EnvSource(),
    dature.JsonSource(file="${@vault.config_path}"),
    schema=Config,
)
