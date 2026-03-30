import abc
from datetime import date, datetime, time
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
    LoadRawResult,
    NameStyle,
    NestedConflict,
    NestedConflicts,
    NestedResolve,
    NestedResolveStrategy,
)

if TYPE_CHECKING:
    from dature.field_path import FieldPath
    from dature.types import TypeLoaderMap


def set_nested(d: dict[str, JSONValue], keys: list[str], value: str) -> None:
    for key in keys[:-1]:
        d = cast("dict[str, JSONValue]", d.setdefault(key, {}))
    d[keys[-1]] = value


class FlatKeyLoader(BaseLoader, abc.ABC):
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
        type_loaders: "TypeLoaderMap | None" = None,
        nested_resolve_strategy: NestedResolveStrategy = "flat",
        nested_resolve: NestedResolve | None = None,
    ) -> None:
        self._split_symbols = split_symbols
        self._nested_resolve_strategy = nested_resolve_strategy
        self._nested_resolve = nested_resolve
        super().__init__(
            prefix=prefix,
            name_style=name_style,
            field_mapping=field_mapping,
            root_validators=root_validators,
            validators=validators,
            expand_env_vars=expand_env_vars,
            type_loaders=type_loaders,
        )

    def _resolve_field_strategy(self, field_name: str) -> NestedResolveStrategy:
        if self._nested_resolve is not None:
            for strategy, field_paths in self._nested_resolve.items():
                for fp in field_paths:
                    if self._field_path_matches(fp, field_name):
                        return strategy
        return self._nested_resolve_strategy

    @staticmethod
    def _field_path_matches(fp: "FieldPath", field_name: str) -> bool:
        if not fp.parts:
            return True
        return fp.parts[0] == field_name

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

    @staticmethod
    def _resolve_var_name(
        field_path: list[str],
        prefix: str | None,
        split_symbols: str,
        conflict: NestedConflict | None,
    ) -> str:
        def _build_name(parts: list[str]) -> str:
            var = split_symbols.join(p.upper() for p in parts)
            if prefix is not None:
                return prefix + var
            return var

        json_var = _build_name(field_path[:1])
        if conflict is not None and conflict.used_var == json_var:
            return json_var
        return _build_name(field_path)

    def _build_var_name(self, key: str) -> str:
        if self._prefix:
            return self._prefix + key.upper()
        return key.upper()

    def _build_nested_var_name(self, top_field: str, nested: dict[str, JSONValue]) -> str:
        for sub_key in nested:
            full_key = f"{top_field}{self._split_symbols}{sub_key}"
            return self._build_var_name(full_key)
        return self._build_var_name(top_field)

    def _pre_process_row(
        self,
        key: str,
        value: str,
        result: dict[str, JSONValue],
        conflicts: NestedConflicts,
    ) -> None:
        parts = key.split(self._split_symbols)
        self._process_key_value(parts=parts, value=value, result=result, conflicts=conflicts)

    def load_raw(self, path: FileOrStream) -> LoadRawResult:
        data = self._load(path)
        data_dict = cast("dict[str, str]", data)
        result: dict[str, JSONValue] = {}
        conflicts: NestedConflicts = {}

        for key, value in data_dict.items():
            self._pre_process_row(key=key, value=value, result=result, conflicts=conflicts)

        expanded = expand_env_vars(result, mode=self._expand_env_vars_mode)
        processed = self._parse_string_values(expanded)
        return LoadRawResult(data=processed, nested_conflicts=conflicts)

    def _process_key_value(
        self,
        *,
        parts: list[str],
        value: str,
        result: dict[str, JSONValue],
        conflicts: NestedConflicts,
    ) -> None:
        if len(parts) > 1:
            top_field = parts[0]
            strategy = self._resolve_field_strategy(top_field)
            existing = result.get(top_field)
            if isinstance(existing, str):
                flat_var = self._build_var_name(self._split_symbols.join(parts))
                json_var = self._build_var_name(top_field)
                if strategy == "flat":
                    result.pop(top_field)
                    set_nested(result, parts, value)
                    conflicts[top_field] = NestedConflict(flat_var, json_var, existing)
                elif strategy == "json":
                    conflicts[top_field] = NestedConflict(json_var, flat_var, existing)
            else:
                set_nested(result, parts, value)
        else:
            top_field = parts[0]
            strategy = self._resolve_field_strategy(top_field)
            existing = result.get(top_field)
            if isinstance(existing, dict):
                json_var = self._build_var_name(top_field)
                flat_var = self._build_nested_var_name(top_field, existing)
                if strategy == "json":
                    result[top_field] = value
                    conflicts[top_field] = NestedConflict(json_var, flat_var, value)
                elif strategy == "flat":
                    conflicts[top_field] = NestedConflict(flat_var, json_var, value)
            else:
                result[top_field] = value
