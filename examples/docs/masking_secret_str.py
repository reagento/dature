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

print(f"api_key (masked): {config.api_key}")  # api_key (masked): **********
print(f"api_key (real): {config.api_key.get_secret_value()}")  # api_key (real): sk-proj-abc123xyz
print(f"host: {config.host}")  # host: api.example.com
print(f"password: {config.password}")  # password: my_secret_password
