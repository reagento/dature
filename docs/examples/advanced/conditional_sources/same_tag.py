"""Conditional sources — same tag, different conditions.

when= enables or disables a Source instance as a whole.  To load some keys
unconditionally and others only in a specific environment, use separate Source
instances with different prefixes or field_mapping= targeting different subsets.

Here base.env (DB_HOST, PORT) is always loaded, while the vault token comes
from the OS environment in prod and from a local file in dev.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ["APP_ENV"] = "dev"

base_env_path = Path(__file__).parent / "sources" / "base.env"
vault_dev_path = Path(__file__).parent / "sources" / "vault_dev.env"


@dataclass
class AppConfig:
    db_host: str = ""
    port: int = 8080
    vault_token: str = ""


cfg = dature.load(
    dature.EnvFileSource(file=str(base_env_path)),  # always — DB_HOST, PORT
    dature.EnvSource(
        tag="secrets", when={"${APP_ENV}": "prod"}
    ),  # prod — VAULT_TOKEN from env
    dature.EnvFileSource(  # dev  — VAULT_TOKEN from file
        tag="secrets",
        file=str(vault_dev_path),
        when={"${APP_ENV}": ("dev", "local")},
    ),
    schema=AppConfig,
)

assert cfg.db_host == "db.internal"
assert cfg.port == 5432
assert cfg.vault_token == "dev-token-from-file"
