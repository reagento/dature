# --8<-- [start:setup]
from dataclasses import dataclass

import dature


@dataclass
class AppConfig:
    vault_token: str = ""


# --8<-- [end:setup]

# --8<-- [start:example]
dature.load(
    dature.EnvSource(),
    dature.EnvSource(prefix="BACKUP_"),  # collision
    dature.VaultSource(path="secret/app", token="${@env.VAULT_TOKEN}"),
    schema=AppConfig,
)

# --8<-- [end:example]
