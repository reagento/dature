"""PaymentCardNumber — validates via Luhn and detects brand."""

from dataclasses import dataclass

from dature.fields.payment_card import PaymentCardNumber


@dataclass
class Config:
    card: PaymentCardNumber


config = Config(card=PaymentCardNumber("4111111111111111"))

print(str(config.card))  # ************1111
print(repr(config.card))  # PaymentCardNumber('************1111')
print(config.card.masked)  # ************1111
print(config.card.brand)  # Visa
print(config.card.get_raw_number())  # 4111111111111111
