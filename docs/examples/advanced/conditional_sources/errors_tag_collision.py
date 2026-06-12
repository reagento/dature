from dataclasses import dataclass

import dature


@dataclass
class AppConfig:
    vault_token: str = ""


dature.load(
    dature.EnvSource(),  # auto-tag = "env"
    dature.EnvSource(prefix="BACKUP_"),  # auto-tag = "env" => collision
    dature.VaultSource(
        path="secret/app",
        token="${@env.VAULT_TOKEN}",  # noqa: S106
    ),
    schema=AppConfig,
)
