"""Conditional sources — toggle from another source.

The toggle value lives in config.json, not in an OS env var.
JsonSource loads first; its "env" key drives the when= of EnvFileSource.
"""

from dataclasses import dataclass
from pathlib import Path

import dature

cfg_path = Path(__file__).parent / "sources" / "config.json"
vault_dev_path = Path(__file__).parent / "sources" / "vault_dev.env"


@dataclass
class AppConfig:
    vault_token: str = ""


cfg = dature.load(
    dature.JsonSource(tag="cfg", file=str(cfg_path)),
    dature.EnvFileSource(
        tag="secrets",
        file=str(vault_dev_path),
        when={"${@cfg.env}": ("dev", "local")},
    ),
    schema=AppConfig,
)

# cfg.env == "dev" → EnvFileSource enabled → token from file
assert cfg.vault_token == "dev-token-from-file"
