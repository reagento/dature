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
