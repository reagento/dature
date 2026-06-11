from pathlib import Path
cfg_path = Path(__file__).parent / "sources" / "config.json"
vault_dev_path = Path(__file__).parent / "sources" / "vault_dev.env"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class AppConfig:
    vault_token: str = ""


cfg = dature.load(
    dature.JsonSource(tag="cfg", file=str(cfg_path)),
    dature.EnvFileSource(
        tag="secrets",
        file=str(vault_dev_path),
        when=dature.When("${@cfg.env}").in_("dev", "local"),
    ),
    schema=AppConfig,
)

assert cfg.vault_token == "dev-token-from-file"
# --8<-- [end:example]