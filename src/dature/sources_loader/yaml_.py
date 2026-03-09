import abc
from datetime import date, datetime, time
from typing import cast

from adaptix import loader
from adaptix.provider import Provider
from ruamel.yaml import YAML
from ruamel.yaml.docinfo import Version

from dature.path_finders.yaml_ import Yaml11PathFinder, Yaml12PathFinder
from dature.sources_loader.base import BaseLoader
from dature.sources_loader.loaders import (
    bytearray_from_string,
    date_passthrough,
    datetime_passthrough,
    time_from_int,
    time_from_string,
)
from dature.types import FILE_LIKE_TYPES, FileOrStream, JSONValue


class BaseYamlLoader(BaseLoader, abc.ABC):
    @abc.abstractmethod
    def _yaml_version(self) -> Version: ...

    def _load(self, path: FileOrStream) -> JSONValue:
        yaml = YAML(typ="safe")
        yaml.version = self._yaml_version()
        if isinstance(path, FILE_LIKE_TYPES):
            return cast("JSONValue", yaml.load(path))
        with path.open() as file_:
            return cast("JSONValue", yaml.load(file_))


class Yaml11Loader(BaseYamlLoader):
    display_name = "yaml1.1"
    path_finder_class = Yaml11PathFinder

    def _yaml_version(self) -> Version:
        return Version(1, 1)

    def _additional_loaders(self) -> list[Provider]:
        return [
            loader(date, date_passthrough),
            loader(datetime, datetime_passthrough),
            loader(time, time_from_int),
            loader(bytearray, bytearray_from_string),
        ]


class Yaml12Loader(BaseYamlLoader):
    display_name = "yaml1.2"
    path_finder_class = Yaml12PathFinder

    def _yaml_version(self) -> Version:
        return Version(1, 2)

    def _additional_loaders(self) -> list[Provider]:
        return [
            loader(date, date_passthrough),
            loader(datetime, datetime_passthrough),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_string),
        ]
