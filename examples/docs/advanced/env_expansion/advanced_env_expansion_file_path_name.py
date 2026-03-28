"""ENV expansion — variable in file name."""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"

os.environ["DATURE_APP_ENV"] = "production"


@dataclass
class Config:
    host: str
    port: int


config = dature.load(
    dature.Source(file=str(SOURCES_DIR / "config.$DATURE_APP_ENV.yaml")),
    dataclass_=Config,
)

assert config.host == "prod.example.com"
assert config.port == 443
