"""PaymentCardNumber — validates via Luhn and detects brand."""

from dataclasses import dataclass

from dature.fields.payment_card import PaymentCardNumber


@dataclass
class Config:
    card: PaymentCardNumber


config = Config(card=PaymentCardNumber("4111111111111111"))

assert str(config.card) == "************1111"
assert repr(config.card) == "PaymentCardNumber('************1111')"
assert config.card.masked == "************1111"
assert config.card.brand == "Visa"
assert config.card.get_raw_number() == "4111111111111111"
