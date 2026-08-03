import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


dature.configure(
    consul={
        "host": os.environ["CONSUL_HOST"],
        "port": int(os.environ["CONSUL_PORT"]),
    },
)

config = dature.load(dature.ConsulSource(path="myapp"), schema=Config)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
