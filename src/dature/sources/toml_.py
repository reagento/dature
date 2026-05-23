import abc
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal, cast

from adaptix import loader
from adaptix.provider import Provider

from dature._descriptors import classproperty
from dature.loaders import (
    bytearray_from_string,
    date_passthrough,
    datetime_passthrough,
    none_from_empty_string,
    optional_from_empty_string,
)
from dature.loaders.toml_ import time_passthrough
from dature.path_finders.base import PathFinder
from dature.sources.base import FileSource
from dature.types import FILE_LIKE_TYPES, FileOrStream, JSONValue

type _TomlVersionStr = Literal["1.0.0", "1.1.0"]


@dataclass(kw_only=True, repr=False)
class _BaseTomlSource(FileSource, abc.ABC):
    @abc.abstractmethod
    def _toml_version(self) -> _TomlVersionStr:
        """Return the TOML spec version this source parses.

        Subclasses return a string literal rather than ``toml_rs._lib.TomlVersion``
        directly so this module can be imported without the ``toml`` extra.
        """

    def _load_file(self, path: FileOrStream) -> JSONValue:
        import toml_rs  # noqa: PLC0415

        if isinstance(path, FILE_LIKE_TYPES):
            content = path.read()
            if isinstance(content, bytes):
                content = content.decode()
            return cast("JSONValue", toml_rs.loads(content, toml_version=self._toml_version()))
        with path.open() as file:
            return cast("JSONValue", toml_rs.loads(file.read(), toml_version=self._toml_version()))

    def additional_loaders(self) -> list[Provider]:
        return [
            loader(date, date_passthrough),
            loader(datetime, datetime_passthrough),
            loader(time, time_passthrough),
            loader(bytearray, bytearray_from_string),
            loader(type(None), none_from_empty_string),
            loader(str | None, optional_from_empty_string),
            loader(Any, optional_from_empty_string),
        ]


@dataclass(kw_only=True, repr=False)
class Toml10Source(_BaseTomlSource):
    format_name = "toml1.0"

    @classproperty
    def path_finder_class(cls) -> type[PathFinder]:  # noqa: N805
        from dature.path_finders.toml_ import Toml10PathFinder  # noqa: PLC0415

        return Toml10PathFinder

    def _toml_version(self) -> _TomlVersionStr:
        return "1.0.0"


@dataclass(kw_only=True, repr=False)
class Toml11Source(_BaseTomlSource):
    format_name = "toml1.1"

    @classproperty
    def path_finder_class(cls) -> type[PathFinder]:  # noqa: N805
        from dature.path_finders.toml_ import Toml11PathFinder  # noqa: PLC0415

        return Toml11PathFinder

    def _toml_version(self) -> _TomlVersionStr:
        return "1.1.0"
