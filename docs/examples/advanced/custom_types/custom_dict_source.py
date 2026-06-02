"""Custom source — subclass Source to load from a plain dict."""

from dataclasses import dataclass
from typing import Any, cast

import dature
from dature.sources.base import Source
from dature.types import JSONValue


@dataclass(kw_only=True, repr=False)
class DictSource(Source):
    format_name = "dict"
    data: dict[str, Any]

    def _load(self) -> JSONValue:
        return cast("JSONValue", self.data)


@dataclass
class Config:
    host: str
    port: int


config = dature.load(
    DictSource(data={"host": "localhost", "port": 8080}),
    schema=Config,
)

assert config == Config(host="localhost", port=8080)
