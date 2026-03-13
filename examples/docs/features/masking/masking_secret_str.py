"""SecretStr & PaymentCardNumber — masked values in debug logs."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

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
    assert str(exc) == dedent("""\
    Config loading errors (1)

      [card_number]  Card number must contain only digits
       └── FILE '/Users/n.vidov/Desktop/не work/dature/examples/docs/features/masking/sources/masking_secret_str.yaml', line 2
           card_number: "no*****er"
    """)
else:
    raise AssertionError("Expected DatureConfigError")
