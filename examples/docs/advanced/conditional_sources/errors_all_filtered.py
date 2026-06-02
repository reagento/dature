"""Conditional sources — error: all sources filtered out.

APP_ENV is not set, so ${APP_ENV} expands to "" which matches neither "prod"
nor ("dev", "local"). dature raises DatureError at construction time.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ.pop("APP_ENV", None)
dev_env_path = Path(__file__).parent / "sources" / "vault_dev.env"


@dataclass
class SecretsConfig:
    vault_token: str = ""


dature.load(
    dature.EnvSource(tag="secrets", when={"${APP_ENV}": "prod"}),
    dature.EnvFileSource(
        tag="secrets", file=dev_env_path, when={"${APP_ENV}": ("dev", "local")}
    ),
    schema=SecretsConfig,
)
