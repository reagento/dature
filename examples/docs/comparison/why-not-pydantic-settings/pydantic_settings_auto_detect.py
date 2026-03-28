"""dature vs pydantic-settings — auto-detection of file format."""

from dataclasses import dataclass
from pathlib import Path

from dature import Source, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int


# --8<-- [start:auto-detect]
# Just change the file — dature picks the right loader
yaml_config = load(Source(file=SOURCES_DIR / "pydantic_settings_auto_detect.yaml"), Config)
toml_config = load(Source(file=SOURCES_DIR / "pydantic_settings_auto_detect.toml"), Config)
json5_config = load(Source(file=SOURCES_DIR / "pydantic_settings_auto_detect.json5"), Config)
# --8<-- [end:auto-detect]

assert yaml_config.host == "localhost"
assert toml_config.host == "localhost"
assert json5_config.host == "localhost"
