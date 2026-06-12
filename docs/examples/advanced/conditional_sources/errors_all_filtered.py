from pathlib import Path
dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"

# --8<-- [start:example]
import os
from dataclasses import dataclass

import dature

os.environ.pop("APP_ENV", None)


@dataclass
class SecretsConfig:
    vault_token: str = ""


dature.load(
    dature.EnvSource(tag="secrets", when=dature.When("${APP_ENV}") == "prod"),
    dature.EnvFileSource(
        tag="secrets",
        file=dev_env_path,
        when=dature.When("${APP_ENV}").in_("dev", "local"),
    ),
    schema=SecretsConfig,
)
# --8<-- [end:example]
