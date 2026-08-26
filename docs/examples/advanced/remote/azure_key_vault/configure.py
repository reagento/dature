import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


conf = dature.Dature(
    azure_key_vault={
        "vault_url": os.environ["AZURE_KEY_VAULT_URL"],
    },
)

config = conf.load(dature.AzureKeyVaultSource(), schema=Config)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
