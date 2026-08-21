import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


conf = dature.Dature(
    ssm={
        "region_name": os.environ["SSM_REGION_NAME"],
        "endpoint_url": os.environ["SSM_ENDPOINT_URL"],
    },
)

config = conf.load(dature.AwsSsmSource(path="/myapp"), schema=Config)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
