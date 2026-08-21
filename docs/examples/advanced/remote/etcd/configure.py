import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


conf = dature.Dature(
    etcd={
        "host": os.environ["ETCD_HOST"],
        "port": int(os.environ["ETCD_PORT"]),
    },
)

config = conf.load(dature.EtcdSource(path="myapp"), schema=Config)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
