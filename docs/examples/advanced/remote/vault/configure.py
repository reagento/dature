import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


dature.configure(
    vault={
        "host": os.environ["VAULT_HOST"],
        "port": int(os.environ["VAULT_PORT"]),
        "scheme": os.environ["VAULT_SCHEME"],
        "token": os.environ["VAULT_TOKEN"],
    },
)

config = dature.load(dature.VaultSource(path="myapp/config"), schema=Config)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
