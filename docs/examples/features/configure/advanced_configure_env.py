# --8<-- [start:setup]
import os
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"
os.environ["DATURE_LOADING__DEBUG"] = "true"

@dataclass
class Config:
    host: str
    port: int
    debug: bool = False
# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_app.yaml"),
    schema=Config
)
report = dature.get_load_report(config)  # DATURE_LOADING__DEBUG=true — debug enabled
assert report is not None
# --8<-- [end:example]