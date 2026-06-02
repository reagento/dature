"""Function-mode caching via an explicit ``Loader``.

``dature.load(...)`` is a thin shortcut that creates a throwaway ``Loader`` and
calls ``.load()`` once — repeated calls do NOT share a cache. To make caching
useful in function mode, keep the ``Loader`` instance around and call
``.load()`` multiple times.
"""

import os
from dataclasses import dataclass
from datetime import timedelta

import dature

os.environ["FN_HOST"] = "localhost"
os.environ["FN_PORT"] = "6379"


@dataclass
class FunctionConfig:
    host: str
    port: int


loader = dature.Loader(
    dature.EnvSource(prefix="FN_"),
    schema=FunctionConfig,
    cache=timedelta(seconds=30),
)

first = loader.load()
os.environ["FN_PORT"] = "9999"
second = loader.load()

assert first.port == 6379
assert second.port == 6379  # cache still fresh — same Loader instance
