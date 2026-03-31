from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MinItems:
    value: int
    error_message: str = field(default="Value must have at least {value} items", kw_only=True)

    def get_validator_func(self) -> Callable[[Sequence[Any]], bool]:
        def validate(val: Sequence[Any]) -> bool:
            return len(val) >= self.value

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)


@dataclass(frozen=True, slots=True)
class MaxItems:
    value: int
    error_message: str = field(default="Value must have at most {value} items", kw_only=True)

    def get_validator_func(self) -> Callable[[Sequence[Any]], bool]:
        def validate(val: Sequence[Any]) -> bool:
            return len(val) <= self.value

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)


@dataclass(frozen=True, slots=True)
class UniqueItems:
    error_message: str = field(default="Value must contain unique items", kw_only=True)

    def get_validator_func(self) -> Callable[[Sequence[Any]], bool]:
        def validate(val: Sequence[Any]) -> bool:
            return len(val) == len(set(val))

        return validate

    def get_error_message(self) -> str:
        return self.error_message
