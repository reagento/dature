import re
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MinLength:
    value: int
    error_message: str = field(default="Value must have at least {value} characters", kw_only=True)

    def get_validator_func(self) -> Callable[[str], bool]:
        def validate(val: str) -> bool:
            return len(val) >= self.value

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)


@dataclass(frozen=True, slots=True)
class MaxLength:
    value: int
    error_message: str = field(default="Value must have at most {value} characters", kw_only=True)

    def get_validator_func(self) -> Callable[[str], bool]:
        def validate(val: str) -> bool:
            return len(val) <= self.value

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)


@dataclass(frozen=True, slots=True)
class RegexPattern:
    pattern: str
    error_message: str = field(default="Value must match pattern '{pattern}'", kw_only=True)

    def get_validator_func(self) -> Callable[[str], bool]:
        def validate(val: str) -> bool:
            return bool(re.match(self.pattern, val))

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(pattern=self.pattern)
