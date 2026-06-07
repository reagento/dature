"""Conditional sources — error: tag collision (explicit tag=).

APP_ENV is not set. Both when= conditions fire simultaneously because they
use different defaults, leaving two sources enabled under the same explicit
tag="secrets".

Unlike a tag collision caused by ${@tag.key} references, dature detects
this at construction time whenever tag= is set explicitly — no consumer
source needed.

Fix: use the same default in both keys — see the no APP_ENV example.
"""

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
