"""SecretStr & PaymentCardNumber — masked values in debug logs."""

from dataclasses import dataclass
from pathlib import Path

import dature
from dature.errors import DatureConfigError
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_key: SecretStr
    card_number: PaymentCardNumber
    host: str


try:
    config = dature.load(
        dature.Source(file=SOURCES_DIR / "masking_secret_str.yaml"),
        dataclass_=Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "masking_secret_str.yaml")
    assert str(exc) == "Config loading errors (1)"
    assert len(exc.exceptions) == 1
    assert str(exc.exceptions[0]) == (
        "  [card_number]  Card number must contain only digits\n"
        f'   ├── card_number: "<REDACTED>"\n'
        "   │                 ^^^^^^^^^^\n"
        f"   └── FILE '{source}', line 2"
    )
else:
    raise AssertionError("Expected DatureConfigError")
