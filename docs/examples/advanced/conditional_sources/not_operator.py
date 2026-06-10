# --8<-- [start:setup]
import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ["APP_ENV"] = "dev"

dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"


@dataclass
class SecretsConfig:
    vault_token: str = ""


# --8<-- [end:setup]

# --8<-- [start:example]
cfg = dature.load(
    dature.EnvFileSource(
        tag="secrets",
        file=str(dev_env_path),
        when=~(dature.When("${APP_ENV}") == "prod"),  # disabled in prod only
    ),
    schema=SecretsConfig,
)

assert cfg.vault_token == "dev-token-from-file"

# --8<-- [end:example]
