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
        when=dature.When("${@cfg.env}").in_("dev", "local"),
    ),
    schema=AppConfig,
)

assert cfg.vault_token == "dev-token-from-file"