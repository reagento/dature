from pathlib import Path

base_env_path = Path(__file__).parent / "sources" / "base.env"
vault_dev_path = Path(__file__).parent / "sources" / "vault_dev.env"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

os.environ["APP_ENV"] = "dev"


@dataclass
class AppConfig:
    db_host: str = ""
    port: int = 8080
    vault_token: str = ""


cfg = dature.load(
    dature.EnvFileSource(file=str(base_env_path)),  # always — DB_HOST, PORT
    dature.EnvSource(tag="secrets", when=dature.When("${APP_ENV}") == "prod"),
    dature.EnvFileSource(
        tag="secrets",
        file=str(vault_dev_path),
        when=dature.When("${APP_ENV}").in_("dev", "local"),
    ),
    schema=AppConfig,
)

assert cfg.db_host == "db.internal"
assert cfg.port == 5432
assert cfg.vault_token == "dev-token-from-file"
# --8<-- [end:example]
