"""Conditional sources — multiple keys (AND semantics)."""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ["APP_ENV"] = "prod"
os.environ["REGION"] = "eu"

dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"


@dataclass
class SecretsConfig:
    vault_token: str = ""


cfg = dature.load(
    dature.EnvFileSource(
        tag="secrets",
        file=str(dev_env_path),
        when={
            "${APP_ENV}": "prod",
            "${REGION}": ("eu", "us"),  # both keys must match
        },
    ),
    schema=SecretsConfig,
)

assert cfg.vault_token == "dev-token-from-file"
