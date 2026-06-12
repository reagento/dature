import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str

config = dature.load(
    dature.VaultSource(
        url=os.environ["VAULT_ADDR"],
        token=os.environ["VAULT_TOKEN"],
        path="myapp/config",
    ),
    schema=Config,
)

assert config == Config(
                 db_password="s3cret", port=5432, name="myapp")  # noqa: S106
