"""SecretStr & PaymentCardNumber — mask sensitive values in str() and repr()."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_key: SecretStr
    password: str
    host: str
    card_number: PaymentCardNumber
    metadata: str


config = load(LoadMetadata(file_=SOURCES_DIR / "secrets.yaml"), Config)

print(f"api_key (masked): {config.api_key}")  # api_key (masked): **********
print(f"api_key (real): {config.api_key.get_secret_value()}")  # api_key (real): sk-proj-abc123def456
print(f"host: {config.host}")  # host: api.example.com
print(f"password: {config.password}")  # password: **********
print(f"card (masked): {config.card_number}")  # card (masked): ************1111
print(f"card brand: {config.card_number.brand}")  # card brand: Visa
print(f"metadata: {config.metadata}")  # metadata: aK9$mP2xL5vQ8wR3nJ7yB4zT6
