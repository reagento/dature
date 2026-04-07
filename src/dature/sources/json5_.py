import io
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import TYPE_CHECKING, TextIO, cast

from adaptix import loader
from adaptix.provider import Provider

from dature._descriptors import classproperty
from dature.sources.base import FileSource

if TYPE_CHECKING:
    from dature.path_finders.base import PathFinder
from dature.loaders import (
    bytearray_from_string,
    date_from_string,
    datetime_from_string,
    float_from_string,
    time_from_string,
)
from dature.loaders.json5_ import str_from_json_identifier
from dature.types import BINARY_IO_TYPES, TEXT_IO_TYPES, FileOrStream, JSONValue


@dataclass(kw_only=True, repr=False)
class Json5Source(FileSource):
    format_name = "json5"

    @classproperty
    def path_finder_class(cls) -> "type[PathFinder]":  # noqa: N805
        from dature.path_finders.json5_ import Json5PathFinder  # noqa: PLC0415

        return Json5PathFinder

    def additional_loaders(self) -> list[Provider]:
        return [
            loader(str, str_from_json_identifier),
            loader(float, float_from_string),
            loader(date, date_from_string),
            loader(datetime, datetime_from_string),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_string),
        ]

    def _load_file(self, path: FileOrStream) -> JSONValue:
        import json5  # noqa: PLC0415

        if isinstance(path, TEXT_IO_TYPES):
            return cast("JSONValue", json5.load(cast("TextIO", path)))
        if isinstance(path, BINARY_IO_TYPES):
            return cast("JSONValue", json5.load(io.TextIOWrapper(cast("io.BufferedReader", path))))
        with path.open() as file:
            return cast("JSONValue", json5.load(file))
