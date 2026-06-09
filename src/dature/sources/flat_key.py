"""FlatKeySource: env-var / CLI style sources with ``__`` nesting."""

import abc
from dataclasses import dataclass
from typing import cast

from adaptix.provider import Provider

from dature.errors import CaretSpan
from dature.expansion.env_expand import expand_env_vars
from dature.field_path import FieldPath
from dature.sources.base import Source, string_value_loaders
from dature.sources.presentation import (
    find_value_in_line,
    resolve_var_name,
    value_line_carets,
)
from dature.type_aliases import (
    JSONValue,
    LoadRawResult,
    NestedConflict,
    NestedConflicts,
    NestedResolve,
    NestedResolveStrategy,
)


# --8<-- [start:flat-key-source]
@dataclass(kw_only=True, repr=False)
class FlatKeySource(Source, abc.ABC):
    nested_sep: str = "__"
    nested_resolve_strategy: "NestedResolveStrategy | None" = None
    nested_resolve: NestedResolve | None = None
    # --8<-- [end:flat-key-source]

    @staticmethod
    def _set_nested(target: dict[str, JSONValue], keys: list[str], value: str) -> None:
        for key in keys[:-1]:
            target = cast("dict[str, JSONValue]", target.setdefault(key, {}))
        target[keys[-1]] = value

    def _resolve_nested_strategy(
        self,
        field_name: str,
        *,
        resolved_nested_strategy: NestedResolveStrategy = "flat",
        resolved_nested_resolve: NestedResolve | None = None,
    ) -> NestedResolveStrategy:
        effective_nested_resolve = (
            resolved_nested_resolve if resolved_nested_resolve is not None else self.nested_resolve
        )
        if effective_nested_resolve is not None:
            for strategy, field_paths in effective_nested_resolve.items():
                paths = field_paths if isinstance(field_paths, tuple) else (field_paths,)
                for field_path in paths:
                    if self._field_path_matches(field_path, field_name):
                        return strategy
        return resolved_nested_strategy

    @staticmethod
    def _field_path_matches(field_path: FieldPath, field_name: str) -> bool:
        if not field_path.parts:
            return True
        return field_path.parts[0] == field_name

    def additional_loaders(self) -> list[Provider]:
        return string_value_loaders()

    @staticmethod
    def _value_line_carets(
        value_lines: list[str],
        value_start: int,
        first_caret: CaretSpan | None = None,
    ) -> list[CaretSpan]:
        return value_line_carets(value_lines, value_start, first_caret)

    @staticmethod
    def _resolve_var_name(
        field_path: list[str],
        prefix: str | None,
        nested_sep: str,
        conflict: NestedConflict | None,
    ) -> str:
        return resolve_var_name(field_path, prefix, nested_sep, conflict)

    @staticmethod
    def _find_value_in_line(
        line: str,
        *,
        input_value: JSONValue,
        field_key: str | None = None,
        search_from: int = 0,
    ) -> CaretSpan | None:
        return find_value_in_line(line, input_value=input_value, field_key=field_key, search_from=search_from)

    def _build_var_name(self, key: str) -> str:
        if self.prefix:
            return self.prefix + key.upper()
        return key.upper()

    def _build_nested_var_name(self, top_field: str, nested: dict[str, JSONValue]) -> str:
        for sub_key in nested:
            full_key = f"{top_field}{self.nested_sep}{sub_key}"
            return self._build_var_name(full_key)
        return self._build_var_name(top_field)

    def _pre_process_row(
        self,
        key: str,
        value: str,
        result: dict[str, JSONValue],
        conflicts: NestedConflicts,
        *,
        resolved_nested_strategy: NestedResolveStrategy = "flat",
        resolved_nested_resolve: NestedResolve | None = None,
    ) -> None:
        parts = key.split(self.nested_sep)
        self._process_key_value(
            parts=parts,
            value=value,
            result=result,
            conflicts=conflicts,
            resolved_nested_strategy=resolved_nested_strategy,
            resolved_nested_resolve=resolved_nested_resolve,
        )

    def load_raw(self) -> LoadRawResult:
        data = self._load()
        data_dict = cast("dict[str, str]", data)
        result: dict[str, JSONValue] = {}
        conflicts: NestedConflicts = {}

        for key, value in data_dict.items():
            self._pre_process_row(
                key=key,
                value=value,
                result=result,
                conflicts=conflicts,
                resolved_nested_strategy=self.nested_resolve_strategy,  # type: ignore[arg-type]
                resolved_nested_resolve=self.nested_resolve,
            )

        expanded = expand_env_vars(result, mode=self.expand_env_vars)  # type: ignore[arg-type]
        processed = self._parse_string_values(expanded)
        return LoadRawResult(data=processed, nested_conflicts=conflicts)

    def _process_key_value(
        self,
        *,
        parts: list[str],
        value: str,
        result: dict[str, JSONValue],
        conflicts: NestedConflicts,
        resolved_nested_strategy: NestedResolveStrategy = "flat",
        resolved_nested_resolve: NestedResolve | None = None,
    ) -> None:
        if len(parts) > 1:
            top_field = parts[0]
            strategy = self._resolve_nested_strategy(
                top_field,
                resolved_nested_strategy=resolved_nested_strategy,
                resolved_nested_resolve=resolved_nested_resolve,
            )
            existing = result.get(top_field)
            if isinstance(existing, str):
                flat_var = self._build_var_name(self.nested_sep.join(parts))
                json_var = self._build_var_name(top_field)
                if strategy == "flat":
                    result.pop(top_field)
                    self._set_nested(result, parts, value)
                    conflicts[top_field] = NestedConflict(flat_var, json_var, existing)
                elif strategy == "json":
                    conflicts[top_field] = NestedConflict(json_var, flat_var, existing)
            else:
                self._set_nested(result, parts, value)
        else:
            top_field = parts[0]
            strategy = self._resolve_nested_strategy(
                top_field,
                resolved_nested_strategy=resolved_nested_strategy,
                resolved_nested_resolve=resolved_nested_resolve,
            )
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
