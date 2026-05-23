import abc
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import cast

from adaptix import loader
from adaptix.provider import Provider

from dature._descriptors import classproperty
from dature.loaders import (
    bytearray_from_string,
    date_passthrough,
    datetime_passthrough,
    time_from_string,
)
from dature.loaders.yaml_ import time_from_int
from dature.path_finders.base import PathFinder
from dature.sources.base import FileSource
from dature.types import FILE_LIKE_TYPES, FileOrStream, JSONValue


@dataclass(kw_only=True, repr=False)
class _BaseYamlSource(FileSource, abc.ABC):
    @abc.abstractmethod
    def _yaml_version(self) -> tuple[int, int]:
        """Return the (major, minor) YAML version this source parses.

        Subclasses return a tuple instead of ``ruamel.yaml.docinfo.Version``
        directly so this module can be imported without the ``yaml`` extra
        installed.
        """

    def _load_file(self, path: FileOrStream) -> JSONValue:
        from ruamel.yaml import YAML  # noqa: PLC0415
        from ruamel.yaml.docinfo import Version  # noqa: PLC0415

        yaml = YAML(typ="safe")
        yaml.version = Version(*self._yaml_version())
        if isinstance(path, FILE_LIKE_TYPES):
            return cast("JSONValue", yaml.load(path))
        with path.open(encoding=self.encoding) as file:
            return cast("JSONValue", yaml.load(file))


@dataclass(kw_only=True, repr=False)
class Yaml11Source(_BaseYamlSource):
    format_name = "yaml1.1"

    @classproperty
    def path_finder_class(cls) -> type[PathFinder]:  # noqa: N805
        from dature.path_finders.yaml_ import Yaml11PathFinder  # noqa: PLC0415

        return Yaml11PathFinder

    def _yaml_version(self) -> tuple[int, int]:
        return (1, 1)

    def additional_loaders(self) -> list[Provider]:
        return [
            loader(date, date_passthrough),
            loader(datetime, datetime_passthrough),
            loader(time, time_from_int),
            loader(bytearray, bytearray_from_string),
        ]


@dataclass(kw_only=True, repr=False)
class Yaml12Source(_BaseYamlSource):
    format_name = "yaml1.2"

    @classproperty
    def path_finder_class(cls) -> type[PathFinder]:  # noqa: N805
        from dature.path_finders.yaml_ import Yaml12PathFinder  # noqa: PLC0415

        return Yaml12PathFinder

    def _yaml_version(self) -> tuple[int, int]:
        return (1, 2)

    def additional_loaders(self) -> list[Provider]:
        return [
            loader(date, date_passthrough),
            loader(datetime, datetime_passthrough),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_string),
        ]
