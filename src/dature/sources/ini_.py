import configparser
import io
from dataclasses import dataclass
from typing import cast

from adaptix.provider import Provider

from dature.expansion.env_expand import expand_env_vars
from dature.path_finders.ini_ import TablePathFinder
from dature.sources.base import FileSource, _string_value_loaders
from dature.types import BINARY_IO_TYPES, TEXT_IO_TYPES, ExpandEnvVarsMode, FileOrStream, JSONValue


@dataclass(kw_only=True, repr=False)
class IniSource(FileSource):
    format_name = "ini"
    path_finder_class = TablePathFinder

    def additional_loaders(self) -> list[Provider]:
        return _string_value_loaders()

    def _pre_processing(
        self,
        data: JSONValue,
        *,
        resolved_expand: ExpandEnvVarsMode,
    ) -> JSONValue:
        prefixed = self._apply_prefix(data)
        expanded = expand_env_vars(prefixed, mode=resolved_expand)
        return self._parse_string_values(expanded)

    def _load_file(self, path: FileOrStream) -> JSONValue:
        config = configparser.ConfigParser(interpolation=None)
        if isinstance(path, TEXT_IO_TYPES):
            config.read_file(path)
        elif isinstance(path, BINARY_IO_TYPES):
            config.read_file(io.TextIOWrapper(cast("io.BufferedReader", path)))
        else:
            with path.open() as f:
                config.read_file(f)
        if self.prefix and self.prefix in config:
            result: dict[str, JSONValue] = dict(config[self.prefix])
            child_prefix = self.prefix + "."
            for section in config.sections():
                if section.startswith(child_prefix):
                    nested_key = section[len(child_prefix) :]
                    result[nested_key] = dict(config[section])
            return {self.prefix: result}

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
