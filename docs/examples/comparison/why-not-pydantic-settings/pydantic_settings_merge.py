# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "pydantic_settings_merge_defaults.yaml",
    ),
    dature.Yaml12Source(
        file=SOURCES_DIR / "pydantic_settings_merge_local.yaml",
        skip_if_broken=True,
    ),
    dature.EnvSource(prefix="APP_"),
    schema=Config,
)

assert config.host == "localhost"
assert config.port == 9090
# --8<-- [end:example]
