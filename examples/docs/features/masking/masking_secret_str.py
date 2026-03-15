"""SecretStr & PaymentCardNumber — masked values in debug logs."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_key: SecretStr
    card_number: PaymentCardNumber
    host: str


try:
    config = load(
        LoadMetadata(file_=SOURCES_DIR / "masking_secret_str.yaml"),
        Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "masking_secret_str.yaml")
    assert str(exc) == "Config loading errors (1)"
    assert len(exc.exceptions) == 1
    assert str(exc.exceptions[0]) == (
        "  [card_number]  Card number must contain only digits\n"
        f"   └── FILE '{source}', line 2\n"
        '       card_number: "no*****er"'
    )
else:
    raise AssertionError("Expected DatureConfigError")
