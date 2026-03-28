"""dature vs pydantic-settings — auto-detection of file format."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


# --8<-- [start:auto-detect]
# Just change the file — dature picks the right loader
yaml_config = dature.load(dature.Source(file=SOURCES_DIR / "pydantic_settings_auto_detect.yaml"), dataclass_=Config)
toml_config = dature.load(dature.Source(file=SOURCES_DIR / "pydantic_settings_auto_detect.toml"), dataclass_=Config)
json5_config = dature.load(dature.Source(file=SOURCES_DIR / "pydantic_settings_auto_detect.json5"), dataclass_=Config)
# --8<-- [end:auto-detect]

assert yaml_config.host == "localhost"
assert toml_config.host == "localhost"
assert json5_config.host == "localhost"
