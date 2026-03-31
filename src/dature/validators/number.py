from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Gt:
    value: int | float
    error_message: str = field(default="Value must be greater than {value}", kw_only=True)

    def get_validator_func(self) -> Callable[[int | float], bool]:
        def validate(val: float) -> bool:
            return val > self.value

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)


@dataclass(frozen=True, slots=True)
class Ge:
    value: int | float
    error_message: str = field(default="Value must be greater than or equal to {value}", kw_only=True)

    def get_validator_func(self) -> Callable[[int | float], bool]:
        def validate(val: float) -> bool:
            return val >= self.value

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)


@dataclass(frozen=True, slots=True)
class Lt:
    value: int | float
    error_message: str = field(default="Value must be less than {value}", kw_only=True)

    def get_validator_func(self) -> Callable[[int | float], bool]:
        def validate(val: float) -> bool:
            return val < self.value

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)


@dataclass(frozen=True, slots=True)
class Le:
    value: int | float
    error_message: str = field(default="Value must be less than or equal to {value}", kw_only=True)

    def get_validator_func(self) -> Callable[[int | float], bool]:
        def validate(val: float) -> bool:
            return val <= self.value

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)
