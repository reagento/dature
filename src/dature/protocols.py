from dataclasses import Field
from typing import Any, ClassVar, Protocol, runtime_checkable


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


@runtime_checkable
class ChecksInvariants(Protocol):
    """Sources that override ``check_invariants`` to validate post-merge state."""

    def check_invariants(self) -> None: ...
