"""Custom validator — error example."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import dature
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Ge

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass(frozen=True, slots=True)
class Divisible:
    value: int
    error_message: str = "Value must be divisible by {value}"

    def get_validator_func(self) -> Callable[[int], bool]:
        def validate(val: int) -> bool:
            return val % self.value == 0

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)


@dataclass
class ServiceConfig:
    port: int
    name: str
    tags: list[str]
    workers: Annotated[int, Ge(1), Divisible(2)]


try:
    dature.load(
        dature.Source(file=SOURCES_DIR / "validation_custom_invalid.json5"),
        dataclass_=ServiceConfig,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "validation_custom_invalid.json5")
    assert str(exc) == "ServiceConfig loading errors (1)"
    assert len(exc.exceptions) == 1
    assert str(exc.exceptions[0]) == (
        f"  [workers]  Value must be divisible by 2\n"
        f"   ├── workers: 3,\n"
        f"   │            ^\n"
        f"   └── FILE '{source}', line 5"
    )
