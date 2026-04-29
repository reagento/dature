"""Root validator: ``V.root(func)`` — cross-field checks.

``RootPredicate`` is intentionally **not** a :class:`Predicate`. Placing it in
``Annotated[...]`` metadata raises a ``TypeError`` at retort-build time — it may
only appear in ``Source.root_validators``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import final


@final
@dataclass(frozen=True, slots=True)
class RootPredicate:
    func: Callable[..., bool]
    error_message: str = "Root validation failed"

    def get_validator_func(self) -> Callable[..., bool]:
        return self.func

    def get_error_message(self) -> str:
        return self.error_message
