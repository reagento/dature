"""Cross-source references — error: cycle."""

from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str = ""


# EnvSource depends on JsonSource (via prefix) and JsonSource depends on
# EnvSource (via file) — dature detects the cycle and raises immediately.
dature.load(
    dature.EnvSource(prefix="${@json.prefix_key}"),
    dature.JsonSource(file="${@env.config_path}"),
    schema=Config,
)
