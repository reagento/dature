import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    db_password: str
    port: int
    name: str


config = dature.load(
    dature.AzureAppConfigSource(
        endpoint=os.environ["AZURE_APP_CONFIG_ENDPOINT"],
        key_filter="myapp:*",
        prefix="myapp",
    ),
    schema=Config,
)

assert config == Config(db_password="s3cret", port=5432, name="myapp")  # noqa: S106
