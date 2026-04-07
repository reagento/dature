from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dature.path_finders.base import PathFinder


class classproperty:  # noqa: N801
    def __init__(self, func: Callable[..., "type[PathFinder]"]) -> None:
        self.fget = func

    def __get__(self, obj: object | None, owner: type) -> "type[PathFinder]":
        return self.fget(owner)
