from pathlib import Path
dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

os.environ["APP_ENV"] = "prod"
os.environ["REGION"] = "eu"


@dataclass
class SecretsConfig:
    vault_token: str = ""


cfg = dature.load(
    dature.EnvFileSource(
        tag="secrets",
        file=str(dev_env_path),
        when=(
            (dature.When("${APP_ENV}") == "prod")
            & dature.When("${REGION}").in_("eu", "us")
        ),
    ),
    schema=SecretsConfig,
)

assert cfg.vault_token == "dev-token-from-file"
# --8<-- [end:example]