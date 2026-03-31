import abc

from dature.errors import LineRange


class PathFinder(abc.ABC):
    @abc.abstractmethod
    def __init__(self, content: str) -> None: ...

    @abc.abstractmethod
    def find_line_range(self, target_path: list[str]) -> LineRange | None: ...
