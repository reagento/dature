import os
import threading
from dataclasses import dataclass

import dature
from dature import FixedIntervalTrigger

# --8<-- [start:example]
os.environ["SERVICE_NAME"] = "billing"

reloaded = threading.Event()


@dature.load(
    dature.EnvSource(prefix="SERVICE_"),
    cache=True,
    reload=FixedIntervalTrigger(interval=0.1),
    on_reload=lambda _: reloaded.set(),
)
@dataclass
class ServiceConfig:
    name: str


assert ServiceConfig().name == "billing"

# The env var changes — the trigger picks it up on its next tick, without
# anyone calling load() again.
os.environ["SERVICE_NAME"] = "payments"
assert reloaded.wait(5.0), "FixedIntervalTrigger did not fire in time"
assert ServiceConfig().name == "payments"
# --8<-- [end:example]
