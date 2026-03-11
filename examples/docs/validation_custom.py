"""Custom validator — error example."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Annotated

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Ge

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass(frozen=True, slots=True, kw_only=True)
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
    workers: Annotated[int, Ge(value=1), Divisible(value=2)]


try:
    load(
        LoadMetadata(file_=SOURCES_DIR / "validation_custom_invalid.json5"),
        ServiceConfig,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "validation_custom_invalid.json5")
    assert str(exc) == dedent(f"""\
        ServiceConfig loading errors (1)

          [workers]  Value must be divisible by 2
           └── FILE '{source}', line 5
               workers: 3,
        """)
