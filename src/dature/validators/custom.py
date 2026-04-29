"""Custom escape-hatch predicate: ``V.check(func, error_message=...)``."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, final

from dature.validators.predicate import Predicate


@final
@dataclass(frozen=True, slots=True)
class CustomPredicate(Predicate):
    """Escape hatch for arbitrary user validators.

    Has no ``check_type`` enforcement — the caller is responsible for making sure
    ``func`` is applicable to the field's runtime value.
    """

    func: Callable[[Any], bool]
    error_message: str

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401, ARG002
        return

    def get_validator_func(self) -> Callable[[Any], bool]:
        return self.func

    def get_error_message(self) -> str:
        return self.error_message
