"""Unit tests for ``V.check`` escape hatch (``CustomPredicate``).

Integration tests (full load() + error formatting) live in ``test_custom_validator.py``.
"""

from dature import V
from dature.validators.custom import CustomPredicate


class TestVCheck:
    def test_returns_custom_predicate(self) -> None:
        pred = V.check(lambda v: v % 5 == 0, error_message="Value must be divisible by 5")
        assert isinstance(pred, CustomPredicate)

    def test_runtime(self) -> None:
        func = V.check(lambda v: v % 5 == 0, error_message="divisible by 5").get_validator_func()
        assert func(10) is True
        assert func(7) is False

    def test_error_message_from_kwarg(self) -> None:
        pred = V.check(lambda _: True, error_message="Value must be divisible by 5")
        assert pred.get_error_message() == "Value must be divisible by 5"
