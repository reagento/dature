"""Cross-source references — error: tag collision."""

from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str = ""


# Both EnvSources resolve to tag='env' (their default format_name).
# As long as 'env' is referenced by another source, dature raises.
dature.load(
    dature.EnvSource(prefix="APP_"),
    dature.EnvSource(prefix="DB_"),
    dature.JsonSource(file="${@env.config_path}"),
    schema=Config,
)
