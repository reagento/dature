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
    LoadMetadata(file_=str(SOURCES_DIR / "camel_case.yaml"), name_style="lower_camel"),
    ApiConfig,
)

print(f"user_name: {config.user_name}")
print(f"max_retries: {config.max_retries}")
print(f"is_active: {config.is_active}")
print(f"base_url: {config.base_url}")
