"""Cross-source references — error: unknown tag."""

from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str = ""
    port: int = 8080


# 'vault' is referenced but no VaultSource (or any source tagged 'vault')
# is listed in the load() call — dature raises immediately.
dature.load(
    dature.EnvSource(),
    dature.JsonSource(file="${@vault.config_path}"),
    schema=Config,
)
