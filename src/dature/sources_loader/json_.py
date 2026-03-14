import json
from datetime import date, datetime, time
from typing import cast

from adaptix import loader
from adaptix.provider import Provider

from dature.path_finders.json_ import JsonPathFinder
from dature.sources_loader.base import BaseLoader
from dature.sources_loader.loaders import (
    bytearray_from_string,
    date_from_string,
    datetime_from_string,
    time_from_string,
)
from dature.types import FILE_LIKE_TYPES, FileOrStream, JSONValue


class JsonLoader(BaseLoader):
    display_name = "json"
    path_finder_class = JsonPathFinder

    def _additional_loaders(self) -> list[Provider]:
        return [
            loader(date, date_from_string),
            loader(datetime, datetime_from_string),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_string),
        ]

    def _load(self, path: FileOrStream) -> JSONValue:
        if isinstance(path, FILE_LIKE_TYPES):
            return cast("JSONValue", json.load(path))
        with path.open() as file_:
            return cast("JSONValue", json.load(file_))
