"""configure() — customize masking globally."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, configure, load
from dature.config import MaskingConfig

SOURCES_DIR = Path(__file__).parent / "sources"

configure(masking=MaskingConfig(secret_field_names=("password", "api_key", "custom_token")))


@dataclass
class Config:
    api_key: str
    password: str
    host: str


config = load(LoadMetadata(file_=str(SOURCES_DIR / "secrets.yaml")), Config)

print(f"host: {config.host}")  # host: api.example.com
print(f"password: {config.password}")  # password: my_secret_password

# Reset to defaults
configure(masking=MaskingConfig())
