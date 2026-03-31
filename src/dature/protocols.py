from collections.abc import Callable
from dataclasses import Field
from pathlib import Path
from typing import Any, ClassVar, Protocol, TypeVar

from adaptix import Retort

from dature.errors import SourceLocation
from dature.path_finders.base import PathFinder
from dature.types import FileOrStream, JSONValue, LoadRawResult, NestedConflict

_T = TypeVar("_T")


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


class ValidatorProtocol(Protocol):
    def get_validator_func(self) -> Callable[..., bool]: ...

    def get_error_message(self) -> str: ...


class LoaderProtocol(Protocol):
    display_name: ClassVar[str]
    display_label: ClassVar[str]
    path_finder_class: type[PathFinder] | None
    retorts: dict[type, Retort]

    def load_raw(self, path: FileOrStream) -> LoadRawResult: ...

    def transform_to_dataclass(self, data: JSONValue, dataclass_: type[_T]) -> _T: ...

    def create_retort(self) -> Retort: ...

    def create_probe_retort(self) -> Retort: ...

    def create_validating_retort(self, dataclass_: type[_T]) -> Retort: ...

    @classmethod
    def resolve_location(
        cls,
        field_path: list[str],
        file_path: Path | None,
        filecontent: str | None,
        prefix: str | None,
        split_symbols: str,
        nested_conflict: NestedConflict | None,
    ) -> list[SourceLocation]: ...
