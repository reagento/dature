"""PaymentCardNumber — validates via Luhn and detects brand."""

from dataclasses import dataclass

from dature.fields.payment_card import PaymentCardNumber


@dataclass
class Config:
    card: PaymentCardNumber


config = Config(card=PaymentCardNumber("42424242424242"))

assert str(config.card) == "**********4242"
assert repr(config.card) == "PaymentCardNumber('**********4242')"
assert config.card.masked == "**********4242"
assert config.card.brand == "Visa"
assert config.card.get_raw_number() == "42424242424242"
