"""SecretStr & PaymentCardNumber — masked values in debug logs."""

from dataclasses import dataclass
from pathlib import Path

import dature
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_key: SecretStr
    card_number: PaymentCardNumber
    host: str


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_secret_str.yaml"),
    schema=Config,
)
