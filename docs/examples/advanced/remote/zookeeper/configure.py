import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


conf = dature.Dature(
    zookeeper={
        "hosts": os.environ["ZK_HOST"],
    },
)

config = conf.load(dature.ZookeeperSource(path="myapp"), schema=Config)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
