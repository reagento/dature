# --8<-- [start:setup]
import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ.pop("APP_ENV", None)
dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"


@dataclass
class SecretsConfig:
    vault_token: str = ""


# --8<-- [end:setup]

# --8<-- [start:example]
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
