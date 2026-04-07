import json
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import cast

from adaptix import loader
from adaptix.provider import Provider

from dature.loaders import (
    bytearray_from_string,
    date_from_string,
    datetime_from_string,
    float_from_string,
    time_from_string,
)
from dature.path_finders.json_ import JsonPathFinder
from dature.sources.base import FileSource
from dature.types import FILE_LIKE_TYPES, FileOrStream, JSONValue


@dataclass(kw_only=True, repr=False)
class JsonSource(FileSource):
    format_name = "json"
    path_finder_class = JsonPathFinder

    def additional_loaders(self) -> list[Provider]:
        return [
            loader(float, float_from_string),
            loader(date, date_from_string),
            loader(datetime, datetime_from_string),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_string),
        ]

    def _load_file(self, path: FileOrStream) -> JSONValue:
        if isinstance(path, FILE_LIKE_TYPES):
            return cast("JSONValue", json.load(path))
        with path.open() as file:
            return cast("JSONValue", json.load(file))
