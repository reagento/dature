"""Conditional sources — OR: enable when any of several conditions match."""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ["APP_ENV"] = "staging"

dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"


@dataclass
class SecretsConfig:
    vault_token: str = ""


cfg = dature.load(
    dature.EnvFileSource(
        tag="secrets",
        file=str(dev_env_path),
        # enabled in prod OR staging
        when=(
            (dature.When("${APP_ENV}") == "prod")
            | (dature.When("${APP_ENV}") == "staging")
        ),
    ),
    schema=SecretsConfig,
)

# APP_ENV=staging satisfies the OR condition → source is active
assert cfg.vault_token == "dev-token-from-file"
