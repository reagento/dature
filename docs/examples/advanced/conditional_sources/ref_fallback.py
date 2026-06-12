from pathlib import Path

config_path = Path(__file__).parent / "sources" / "config.json"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class AppConfig:
    env: str = ""


cfg = dature.load(
    # {"env": "dev"}
    dature.JsonSource(tag="cfg", file=str(config_path)),
    # disabled: "dev" != "prod"
    dature.EnvSource(tag="secrets", when=dature.When("${@cfg.env}") == "prod"),
    # fallback
    dature.JsonSource(file=f"${{@secrets.remote_config:-{config_path}}}"),
    schema=AppConfig,
)

assert cfg.env == "dev"
# --8<-- [end:example]
