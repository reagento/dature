from pathlib import Path
dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

os.environ["APP_ENV"] = "prod"
os.environ["VAULT_TOKEN"] = "prod-token-from-env"


@dataclass
class SecretsConfig:
    vault_token: str = ""


cfg = dature.load(
    dature.EnvSource(tag="secrets", when=dature.When("${APP_ENV}") == "prod"),
    dature.EnvFileSource(
        tag="secrets",
        file=str(dev_env_path),
        when=dature.When("${APP_ENV}").in_("dev", "local"),
    ),
    schema=SecretsConfig,
)

assert cfg.vault_token == "prod-token-from-env"
# --8<-- [end:example]