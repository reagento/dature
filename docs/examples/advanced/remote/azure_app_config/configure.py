import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


conf = dature.Dature(
    azure_app_config={
        "endpoint": os.environ["AZURE_APP_CONFIG_ENDPOINT"],
    },
)

config = conf.load(
    dature.AzureAppConfigSource(key_filter="myapp:*", prefix="myapp"),
    schema=Config,
)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
