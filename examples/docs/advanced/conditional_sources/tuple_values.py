"""Conditional sources — multiple allowed values (tuple)."""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ["APP_ENV"] = "local"

dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"


@dataclass
class SecretsConfig:
    vault_token: str = ""


cfg = dature.load(
    dature.EnvFileSource(
        tag="secrets",
        file=str(dev_env_path),
        when={"${APP_ENV}": ("dev", "local")},  # enabled for either value
    ),
    schema=SecretsConfig,
)

assert cfg.vault_token == "dev-token-from-file"
