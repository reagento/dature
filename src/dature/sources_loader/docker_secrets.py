from datetime import date, datetime, time
from pathlib import Path
from typing import TYPE_CHECKING, cast

from adaptix import loader
from adaptix.provider import Provider

from dature.expansion.env_expand import expand_env_vars
from dature.protocols import ValidatorProtocol
from dature.sources_loader.base import BaseLoader
from dature.sources_loader.loaders import (
    bool_loader,
    bytearray_from_json_string,
    date_from_string,
    datetime_from_string,
    float_from_string,
    none_from_empty_string,
    optional_from_empty_string,
    str_from_scalar,
    time_from_string,
)
from dature.types import (
    DotSeparatedPath,
    ExpandEnvVarsMode,
    FieldMapping,
    FieldValidators,
    FileOrStream,
    JSONValue,
    NameStyle,
)

if TYPE_CHECKING:
    from dature.metadata import TypeLoader


def _set_nested(d: dict[str, JSONValue], keys: list[str], value: str) -> None:
    for key in keys[:-1]:
        d = cast("dict[str, JSONValue]", d.setdefault(key, {}))
    d[keys[-1]] = value


class DockerSecretsLoader(BaseLoader):
    display_name = "docker_secrets"

    def __init__(  # noqa: PLR0913
        self,
        *,
        prefix: DotSeparatedPath | None = None,
        split_symbols: str = "__",
        name_style: NameStyle | None = None,
        field_mapping: FieldMapping | None = None,
        root_validators: tuple[ValidatorProtocol, ...] | None = None,
        validators: FieldValidators | None = None,
        expand_env_vars: ExpandEnvVarsMode = "default",
        type_loaders: "tuple[TypeLoader, ...]" = (),
    ) -> None:
        self._split_symbols = split_symbols
        super().__init__(
            prefix=prefix,
            name_style=name_style,
            field_mapping=field_mapping,
            root_validators=root_validators,
            validators=validators,
            expand_env_vars=expand_env_vars,
            type_loaders=type_loaders,
        )

    def _additional_loaders(self) -> list[Provider]:
        return [
            loader(str, str_from_scalar),
            loader(float, float_from_string),
            loader(date, date_from_string),
            loader(datetime, datetime_from_string),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_json_string),
            loader(type(None), none_from_empty_string),
            loader(str | None, optional_from_empty_string),
            loader(bool, bool_loader),
        ]

    def _load(self, path: FileOrStream) -> JSONValue:
        if not isinstance(path, Path):
            msg = "DockerSecretsLoader does not support file-like objects"
            raise TypeError(msg)

        result: dict[str, JSONValue] = {}

        for entry in sorted(path.iterdir()):
            if not entry.is_file():
                continue

            key = entry.name.lower()
            value = entry.read_text().strip()

            if self._prefix and not key.startswith(self._prefix.lower()):
                continue

            if self._prefix:
                key = key[len(self._prefix) :]

            parts = key.split(self._split_symbols)
            if len(parts) > 1:
                _set_nested(result, parts, value)
            else:
                result[key] = value

        return result

    def _pre_processing(self, data: JSONValue) -> JSONValue:
        expanded = expand_env_vars(data, mode=self._expand_env_vars_mode)
        return self._parse_string_values(expanded)
