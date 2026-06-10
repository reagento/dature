# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

config_path = Path(__file__).parent / "sources" / "config.json"


@dataclass
class AppConfig:
    env: str = ""


# --8<-- [end:setup]

# --8<-- [start:example]
cfg = dature.load(
    dature.JsonSource(tag="cfg", file=str(config_path)),                         # {"env": "dev"}
    dature.EnvSource(tag="secrets", when=dature.When("${@cfg.env}") == "prod"),  # disabled: "dev" != "prod"
    dature.JsonSource(file=f"${{@secrets.remote_config:-{config_path}}}"),       # fallback
    schema=AppConfig,
)

assert cfg.env == "dev"

# --8<-- [end:example]
