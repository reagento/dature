"""Custom RemoteSource subclass — pure Python, no external services."""

from dataclasses import dataclass
from typing import ClassVar

import dature
from dature.sources.remote import RemoteSource
from dature.types import JSONValue


@dataclass(kw_only=True, repr=False)
class InMemorySource(RemoteSource):
    """Demonstrates the RemoteSource contract: override two methods."""

    backend: dict[str, dict[str, JSONValue]]
    key: str

    format_name = "in-memory"
    location_label: ClassVar[str] = "MEMORY"

    def remote_address(self) -> str:
        return f"memory://{self.key}"

    def _fetch(self) -> JSONValue:
        return self.backend[self.key]


@dataclass
class Config:
    db_password: str
    port: int


backend = {"myapp/config": {"db_password": "s3cret", "port": 5432}}
config = dature.load(
    InMemorySource(backend=backend, key="myapp/config"),
    schema=Config,
)

assert config == Config(db_password="s3cret", port=5432)  # noqa: S106
