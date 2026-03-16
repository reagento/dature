import io
from datetime import date, datetime, time
from typing import TextIO, cast

import json5
from adaptix import loader
from adaptix.provider import Provider

from dature.path_finders.json5_ import Json5PathFinder
from dature.sources_loader.base import BaseLoader
from dature.sources_loader.loaders import (
    bytearray_from_string,
    date_from_string,
    datetime_from_string,
    float_from_string,
    time_from_string,
)
from dature.sources_loader.loaders.json5_ import str_from_json_identifier
from dature.types import BINARY_IO_TYPES, TEXT_IO_TYPES, FileOrStream, JSONValue


class Json5Loader(BaseLoader):
    display_name = "json5"
    path_finder_class = Json5PathFinder

    def _additional_loaders(self) -> list[Provider]:
        return [
            loader(str, str_from_json_identifier),
            loader(float, float_from_string),
            loader(date, date_from_string),
            loader(datetime, datetime_from_string),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_string),
        ]

    def _load(self, path: FileOrStream) -> JSONValue:
        if isinstance(path, TEXT_IO_TYPES):
            return cast("JSONValue", json5.load(cast("TextIO", path)))
        if isinstance(path, BINARY_IO_TYPES):
            return cast("JSONValue", json5.load(io.TextIOWrapper(cast("io.BufferedReader", path))))
        with path.open() as file_:
            return cast("JSONValue", json5.load(file_))
