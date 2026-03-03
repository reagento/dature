"""SecretStr — mask sensitive values in str() and repr()."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.fields.secret_str import SecretStr

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_key: SecretStr
    password: str
    host: str


config = load(LoadMetadata(file_=str(SOURCES_DIR / "secrets.yaml")), Config)

print(f"api_key (masked): {config.api_key}")
print(f"api_key (real): {config.api_key.get_secret_value()}")
print(f"host: {config.host}")
print(f"password: {config.password}")
