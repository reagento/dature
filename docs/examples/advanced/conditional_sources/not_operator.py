"""Conditional sources — NOT (~): enable when a condition does NOT match."""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ["APP_ENV"] = "dev"

dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"


@dataclass
class SecretsConfig:
    vault_token: str = ""


cfg = dature.load(
    dature.EnvFileSource(
        tag="secrets",
        file=str(dev_env_path),
        when=~(dature.When("${APP_ENV}") == "prod"),  # disabled in prod only
    ),
    schema=SecretsConfig,
)

# APP_ENV=dev is not "prod" → condition is True → source is active
assert cfg.vault_token == "dev-token-from-file"
