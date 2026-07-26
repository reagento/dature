from dataclasses import dataclass

import dature
from dature.sources.base import RemoteSource
from dature.type_aliases import JSONValue


@dataclass(kw_only=True, repr=False)
class InMemorySource(RemoteSource):
    backend: dict[str, dict[str, JSONValue]]
    key: str

    format_name: str = "in-memory"
    location_label: str = "MEMORY"

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
