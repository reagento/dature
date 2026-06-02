"""Conditional sources — referencing a disabled source with a fallback.

config.json contains {"env": "dev"}.  The "secrets" source is disabled lazily
(its when= depends on ${@cfg.env}) because env != "prod".

Disabled sources still occupy their tag slot in the dependency graph, so
${@secrets.remote_config} is a valid reference — it just resolves to absent.
The :- default kicks in and points to the local config.json instead.
"""

from dataclasses import dataclass
from pathlib import Path

import dature

config_path = Path(__file__).parent / "sources" / "config.json"


@dataclass
class AppConfig:
    env: str = ""


cfg = dature.load(
    dature.JsonSource(tag="cfg", file=str(config_path)),  # {"env": "dev"}
    dature.EnvSource(
        tag="secrets", when={"${@cfg.env}": "prod"}
    ),  # disabled: "dev" != "prod"
    dature.JsonSource(
        file=f"${{@secrets.remote_config:-{config_path}}}"
    ),  # fallback fires
    schema=AppConfig,
)

# secrets disabled → remote_config absent → fallback to config.json → env="dev"
assert cfg.env == "dev"
