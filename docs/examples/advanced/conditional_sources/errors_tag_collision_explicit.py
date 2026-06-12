import os
from dataclasses import dataclass

import dature

os.environ.pop("APP_ENV", None)


@dataclass
class SecretsConfig:
    vault_token: str = ""


dature.load(
    dature.EnvSource(
        tag="secrets",
        when=dature.When("${APP_ENV:-prod}") == "prod",
    ),
    dature.EnvFileSource(
        tag="secrets",
        file="sources/vault_dev.env",
        when=dature.When("${APP_ENV:-dev}").in_("dev", "local"),
    ),
    schema=SecretsConfig,
)
