from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int

yaml_config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "pydantic_settings_formats.yaml"),
    schema=Config,
)
toml_config = dature.load(
    dature.Toml11Source(file=SOURCES_DIR / "pydantic_settings_formats.toml"),
    schema=Config,
)
json5_config = dature.load(
    dature.Json5Source(file=SOURCES_DIR / "pydantic_settings_formats.json5"),
    schema=Config,
)

assert yaml_config.host == "localhost"
assert toml_config.host == "localhost"
assert json5_config.host == "localhost"
# --8<-- [end:example]
