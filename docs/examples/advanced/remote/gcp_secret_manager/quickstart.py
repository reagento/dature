import os
from dataclasses import dataclass

import dature


@dataclass
class Config:
    password: str
    port: int
    name: str


config = dature.load(
    dature.GcpSecretManagerSource(
        project_id=os.environ["GCP_PROJECT_ID"],
    ),
    schema=Config,
)

assert config == Config(password="s3cret", port=5432, name="myapp")  # noqa: S106
