from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr


@dataclass
class Config:
    api_key: SecretStr
    card_number: PaymentCardNumber
    host: str


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_secret_str.yaml"),
    schema=Config,
)
# --8<-- [end:example]
