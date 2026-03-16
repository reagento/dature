import abc
from datetime import date, datetime, time
from typing import Any, cast

import toml_rs
from adaptix import loader
from adaptix.provider import Provider
from toml_rs._lib import TomlVersion

from dature.path_finders.toml_ import Toml10PathFinder, Toml11PathFinder
from dature.sources_loader.base import BaseLoader
from dature.sources_loader.loaders import (
    bytearray_from_string,
    date_passthrough,
    datetime_passthrough,
    none_from_empty_string,
    optional_from_empty_string,
)
from dature.sources_loader.loaders.toml_ import time_passthrough
from dature.types import FILE_LIKE_TYPES, FileOrStream, JSONValue


class BaseTomlLoader(BaseLoader, abc.ABC):
    @abc.abstractmethod
    def _toml_version(self) -> TomlVersion: ...

    def _load(self, path: FileOrStream) -> JSONValue:
        if isinstance(path, FILE_LIKE_TYPES):
            content = path.read()
            if isinstance(content, bytes):
                content = content.decode()
            return cast("JSONValue", toml_rs.loads(content, toml_version=self._toml_version()))
        with path.open() as file_:
            return cast("JSONValue", toml_rs.loads(file_.read(), toml_version=self._toml_version()))

    def _additional_loaders(self) -> list[Provider]:
        return [
            loader(date, date_passthrough),
            loader(datetime, datetime_passthrough),
            loader(time, time_passthrough),
            loader(bytearray, bytearray_from_string),
            loader(type(None), none_from_empty_string),
            loader(str | None, optional_from_empty_string),
            loader(Any, optional_from_empty_string),
        ]


class Toml10Loader(BaseTomlLoader):
    display_name = "toml1.0"
    path_finder_class = Toml10PathFinder

    def _toml_version(self) -> TomlVersion:
        return "1.0.0"


class Toml11Loader(BaseTomlLoader):
    display_name = "toml1.1"
    path_finder_class = Toml11PathFinder

    def _toml_version(self) -> TomlVersion:
        return "1.1.0"
