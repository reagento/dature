"""Conditional sources — error: tag collision (auto-tag, consumer reference).

Two EnvSources share the same auto-tag "env" (no tag= set explicitly).
Without a consumer, dature does not notice — but when VaultSource references
${@env.VAULT_TOKEN}, the ambiguous tag is detected and DatureError is raised.

Fix: assign an explicit tag= to at least one EnvSource.
"""

from dataclasses import dataclass

import dature


@dataclass
class AppConfig:
    vault_token: str = ""


dature.load(
    dature.EnvSource(),  # auto-tag "env"
    dature.EnvSource(prefix="BACKUP_"),  # auto-tag "env" — collision!
    dature.VaultSource(path="secret/app", token="${@env.VAULT_TOKEN}"),  # noqa: S106
    schema=AppConfig,
)
