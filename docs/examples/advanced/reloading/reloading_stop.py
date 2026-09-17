import os
import threading
from dataclasses import dataclass

import dature
from dature import FixedIntervalTrigger, Loader

# --8<-- [start:example]
os.environ["SERVICE_NAME"] = "billing"


@dataclass
class ServiceConfig:
    name: str


reloaded = threading.Event()

loader = Loader(
    dature.EnvSource(prefix="SERVICE_"),
    schema=ServiceConfig,
    cache=True,
    reload=FixedIntervalTrigger(interval=0.1),
    on_reload=lambda _: reloaded.set(),
)
assert loader.load().name == "billing"

loader.stop_reload()

# No trigger left to pick up this change — the cached instance never updates.
os.environ["SERVICE_NAME"] = "payments"
assert not reloaded.wait(0.5)
assert loader.load().name == "billing"
# --8<-- [end:example]
