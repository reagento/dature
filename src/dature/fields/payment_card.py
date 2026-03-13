from typing import ClassVar


class PaymentCardNumber:
    __slots__ = ("_number",)

    _MIN_LENGTH: ClassVar[int] = 12
    _MAX_LENGTH: ClassVar[int] = 19
    _LUHN_DOUBLE_THRESHOLD: ClassVar[int] = 9

    _BRAND_RULES: ClassVar[list[tuple[str, int, int, int]]] = [
        # 6 digits
        ("Verve", 6, 506099, 506198),
        ("Verve", 6, 650002, 650027),
        ("Discover", 6, 622126, 622925),
        # 4 digits
        ("Mir", 4, 2200, 2204),
        ("JCB", 4, 3528, 3589),
        ("Mastercard", 4, 2221, 2720),
        ("Discover", 4, 6011, 6011),
        ("Maestro", 4, 5018, 5018),
        ("Maestro", 4, 5020, 5020),
        ("Maestro", 4, 5038, 5038),
        ("Maestro", 4, 5893, 5893),
        ("Maestro", 4, 6304, 6304),
        ("Maestro", 4, 6759, 6759),
        ("Maestro", 4, 6761, 6763),
        ("Troy", 4, 9792, 9792),
        # 3 digits
        ("Diners Club", 3, 300, 305),
        ("Discover", 3, 644, 649),
        # 2 digits
        ("American Express", 2, 34, 34),
        ("American Express", 2, 37, 37),
        ("Mastercard", 2, 51, 55),
        ("RuPay", 2, 60, 60),
        ("UnionPay", 2, 62, 62),
        ("Discover", 2, 65, 65),
        ("Diners Club", 2, 36, 36),
        ("Diners Club", 2, 38, 38),
        ("Maestro", 2, 67, 67),
        # 1 digit
        ("Visa", 1, 4, 4),
    ]

    def __init__(self, card_number: str) -> None:
        cleaned = card_number.replace(" ", "").replace("-", "")

        if not cleaned.isdigit():
            msg = "Card number must contain only digits"
            raise ValueError(msg)

        if not (self._MIN_LENGTH <= len(cleaned) <= self._MAX_LENGTH):
            msg = f"Card number must be {self._MIN_LENGTH}-{self._MAX_LENGTH} digits, got {len(cleaned)}"
            raise ValueError(msg)

        if not self._luhn_check(cleaned):
            msg = "Card number failed Luhn check"
            raise ValueError(msg)

        self._number = cleaned

    def get_raw_number(self) -> str:
        return self._number

    @staticmethod
    def _luhn_check(number: str) -> bool:
        total = 0
        for i, digit_char in enumerate(reversed(number)):
            digit = int(digit_char)
            if i % 2 == 1:
                digit *= 2
                if digit > PaymentCardNumber._LUHN_DOUBLE_THRESHOLD:
                    digit -= PaymentCardNumber._LUHN_DOUBLE_THRESHOLD
            total += digit
        return total % 10 == 0

    @property
    def masked(self) -> str:
        return "*" * (len(self._number) - 4) + self._number[-4:]

    @property
    def brand(self) -> str:
        for brand_name, prefix_len, prefix_min, prefix_max in self._BRAND_RULES:
            if len(self._number) < prefix_len:
                continue
            prefix = int(self._number[:prefix_len])
            if prefix_min <= prefix <= prefix_max:
                return brand_name
        return "Unknown"

    def __str__(self) -> str:
        return self.masked

    def __repr__(self) -> str:
        return f"PaymentCardNumber('{self.masked}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PaymentCardNumber):
            return NotImplemented
        return self._number == other._number

    def __hash__(self) -> int:
        return hash(self._number)
