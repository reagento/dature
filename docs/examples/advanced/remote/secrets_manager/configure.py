import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


dature.configure(
    secrets_manager={
        "region_name": os.environ["SECRETS_MANAGER_REGION_NAME"],
        "endpoint_url": os.environ["SECRETS_MANAGER_ENDPOINT_URL"],
    },
)

source = dature.AwsSecretsManagerSource(name="myapp/config")
config = dature.load(source, schema=Config)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
