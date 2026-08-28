import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    password: str
    port: int
    name: str


conf = dature.Dature(
    gcp_secret_manager={
        "project_id": os.environ["GCP_PROJECT_ID"],
    },
)

config = conf.load(dature.GcpSecretManagerSource(), schema=Config)

assert config == Config(password="s3cret", port=5432, name="myapp")  # noqa: S106
