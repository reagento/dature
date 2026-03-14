"""name_style — auto-convert camelCase keys to snake_case fields."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class ApiConfig:
    user_name: str
    max_retries: int
    is_active: bool
    base_url: str


config = load(
    LoadMetadata(file_=SOURCES_DIR / "naming_name_style.yaml", name_style="lower_camel"),
    ApiConfig,
)

assert config.user_name == "admin"
assert config.max_retries == 3
assert config.is_active is True
assert config.base_url == "https://api.example.com"
