import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


config = dature.load(
    dature.AwsSecretsManagerSource(
        name="myapp/config",
        region_name=os.environ["SECRETS_MANAGER_REGION_NAME"],
        endpoint_url=os.environ["SECRETS_MANAGER_ENDPOINT_URL"],
    ),
    schema=Config,
)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
