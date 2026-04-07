from collections.abc import Callable
from dataclasses import Field
from typing import Any, ClassVar, Protocol


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


class ValidatorProtocol(Protocol):
    def get_validator_func(self) -> Callable[..., bool]: ...

    def get_error_message(self) -> str: ...
