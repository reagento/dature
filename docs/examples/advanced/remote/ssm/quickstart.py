import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


config = dature.load(
    dature.AwsSsmSource(
        path="/myapp",
        region_name=os.environ["SSM_REGION_NAME"],
        endpoint_url=os.environ["SSM_ENDPOINT_URL"],
    ),
    schema=Config,
)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
