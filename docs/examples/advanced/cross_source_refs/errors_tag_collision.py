from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str = ""

dature.load(
    dature.EnvSource(prefix="APP_"), # resolve to tag = 'env'
    dature.EnvSource(prefix="DB_"),  # resolve to tag = 'env' => collision
    dature.JsonSource(file="${@env.config_path}"),
    schema=Config,
)