import configparser
import io
from datetime import date, datetime, time
from typing import cast

from adaptix import loader
from adaptix.provider import Provider

from dature.expansion.env_expand import expand_env_vars
from dature.path_finders.ini_ import TablePathFinder
from dature.sources_loader.base import BaseLoader
from dature.sources_loader.loaders import (
    bool_loader,
    bytearray_from_json_string,
    date_from_string,
    datetime_from_string,
    none_from_empty_string,
    optional_from_empty_string,
    time_from_string,
)
from dature.types import BINARY_IO_TYPES, TEXT_IO_TYPES, FileOrStream, JSONValue


class IniLoader(BaseLoader):
    display_name = "ini"
    path_finder_class = TablePathFinder

    def _additional_loaders(self) -> list[Provider]:
        return [
            loader(date, date_from_string),
            loader(datetime, datetime_from_string),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_json_string),
            loader(type(None), none_from_empty_string),
            loader(str | None, optional_from_empty_string),
            loader(bool, bool_loader),
        ]

    def _pre_processing(self, data: JSONValue) -> JSONValue:
        prefixed = self._apply_prefix(data)
        expanded = expand_env_vars(prefixed, mode=self._expand_env_vars_mode)
        return self._parse_string_values(expanded)

    def _load(self, path: FileOrStream) -> JSONValue:
        config = configparser.ConfigParser(interpolation=None)
        if isinstance(path, TEXT_IO_TYPES):
            config.read_file(path)
        elif isinstance(path, BINARY_IO_TYPES):
            config.read_file(io.TextIOWrapper(cast("io.BufferedReader", path)))
        else:
            with path.open() as f:
                config.read_file(f)
        if self._prefix and self._prefix in config:
            result: dict[str, JSONValue] = dict(config[self._prefix])
            child_prefix = self._prefix + "."
            for section in config.sections():
                if section.startswith(child_prefix):
                    nested_key = section[len(child_prefix) :]
                    result[nested_key] = dict(config[section])
            return {self._prefix: result}

        all_sections: dict[str, JSONValue] = {}
        if config.defaults():
            all_sections["DEFAULT"] = dict(config.defaults())
        for section in config.sections():
            parts = section.split(".")
            target = all_sections
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = cast("dict[str, JSONValue]", target[part])
            target[parts[-1]] = dict(config[section])
        return all_sections
