# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class ApiConfig:
    user_name: str
    max_retries: int
    is_active: bool
    base_url: str
# --8<-- [end:setup]

# --8<-- [start:example]
config = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "naming_name_style.yaml",
        name_style="lower_camel",
    ),
    schema=ApiConfig,
)

assert config.user_name == "admin"
assert config.max_retries == 3
assert config.is_active is True
assert config.base_url == "https://api.example.com"
# --8<-- [end:example]
