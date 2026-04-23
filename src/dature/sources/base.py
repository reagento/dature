import abc
import json
import logging
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

from dature.config_paths import find_config
from dature.errors import CaretSpan, LineRange, SourceLocation
from dature.expansion.env_expand import expand_env_vars, expand_file_path
from dature.field_path import FieldPath
from dature.path_finders.base import PathFinder
from dature.sources.retort import string_value_loaders
from dature.types import (
    FILE_LIKE_TYPES,
    DotSeparatedPath,
    ExpandEnvVarsMode,
    FileOrStream,
    JSONValue,
    LoadRawResult,
    NestedConflict,
    NestedConflicts,
    NestedResolve,
    NestedResolveStrategy,
)

if TYPE_CHECKING:
    from adaptix import Retort
    from adaptix.provider import Provider

    from dature.protocols import ValidatorProtocol
    from dature.types import (
        FieldMapping,
        FieldValidators,
        FileLike,
        FilePath,
        NameStyle,
        SystemConfigDirsArg,
        TypeLoaderMap,
    )

logger = logging.getLogger("dature")


# --8<-- [start:load-metadata]
@dataclass(kw_only=True, repr=False)
class Source(abc.ABC):
    prefix: "DotSeparatedPath | None" = None
    name_style: "NameStyle | None" = None
    field_mapping: "FieldMapping | None" = None
    root_validators: "tuple[ValidatorProtocol, ...] | None" = None
    validators: "FieldValidators | None" = None
    expand_env_vars: "ExpandEnvVarsMode | None" = None
    skip_if_broken: bool | None = None
    skip_if_invalid: "bool | tuple[FieldPath, ...] | None" = None
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
    type_loaders: "TypeLoaderMap | None" = None
    # --8<-- [end:load-metadata]

    format_name: ClassVar[str]
    location_label: ClassVar[str]
    path_finder_class: ClassVar[type[PathFinder] | None] = None

    retorts: "dict[tuple[type, frozenset[tuple[type, Any]]], Retort]" = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __repr__(self) -> str:
        return self.format_name

    def file_display(self) -> str | None:
        return None

    def file_path_for_errors(self) -> Path | None:
        return None

    def display_name(self) -> str:
        return self.file_display() or self.format_name

    def additional_loaders(self) -> "list[Provider]":
        return []

    @staticmethod
    def _infer_type(value: str) -> JSONValue:
        if value == "":
            return value

        try:
            return cast("JSONValue", json.loads(value))
        except (json.JSONDecodeError, ValueError):
            return value

    @classmethod
    def _parse_string_values(cls, data: JSONValue, *, infer_scalars: bool = False) -> JSONValue:
        if not isinstance(data, dict):
            return data

        result: dict[str, JSONValue] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = cls._parse_string_values(value, infer_scalars=True)
            elif isinstance(value, str) and (infer_scalars or value.startswith(("[", "{"))):
                result[key] = cls._infer_type(value)
            else:
                result[key] = value
        return result

    @abc.abstractmethod
    def _load(self) -> JSONValue: ...

    def _apply_prefix(self, data: JSONValue) -> JSONValue:
        if not self.prefix:
            return data

        for key in self.prefix.split("."):
            if not isinstance(data, dict):
                return {}
            if key not in data:
                return {}
            data = data[key]

        return data

    def _pre_processing(
        self,
        data: JSONValue,
        *,
        resolved_expand: ExpandEnvVarsMode,
    ) -> JSONValue:
        prefixed = self._apply_prefix(data)
        return expand_env_vars(prefixed, mode=resolved_expand)

    def load_raw(self) -> LoadRawResult:
        data = self._load()
        processed = self._pre_processing(data, resolved_expand=self.expand_env_vars)  # type: ignore[arg-type]
        logger.debug(
            "[%s] load_raw: source=%s, raw_keys=%s, after_preprocessing_keys=%s",
            type(self).__name__,
            self.display_name(),
            sorted(data.keys()) if isinstance(data, dict) else "<non-dict>",
            sorted(processed.keys()) if isinstance(processed, dict) else "<non-dict>",
        )
        return LoadRawResult(data=processed)

    @staticmethod
    def _empty_location(location_label: str, file_path: Path | None) -> SourceLocation:
        return SourceLocation(
            location_label=location_label,
            file_path=file_path,
            line_range=None,
            line_content=None,
            env_var_name=None,
        )

    @staticmethod
    def _build_search_path(field_path: list[str], prefix: str | None) -> list[str]:
        if not prefix:
            return field_path
        prefix_parts = prefix.split(".")
        return prefix_parts + field_path

    @staticmethod
    def _find_parent_line_range(finder: PathFinder, search_path: list[str]) -> LineRange | None:
        path = search_path[:-1]
        while path:
            line_range = finder.find_line_range(path)
            if line_range is not None:
                return line_range
            path = path[:-1]
        return None

    @classmethod
    def _strip_common_indent(cls, raw_lines: list[str]) -> list[str]:
        indents = [len(line) - len(line.lstrip()) for line in raw_lines if line.strip()]
        if not indents:
            return raw_lines
        min_indent = min(indents)
        return [line[min_indent:] for line in raw_lines]

    @classmethod
    def _build_value_candidates(cls, input_value: JSONValue) -> list[str]:
        if isinstance(input_value, (list, dict)):
            return [json.dumps(input_value, ensure_ascii=False)]
        if isinstance(input_value, str) and input_value == "":
            return ['""', "''"]
        text = str(input_value)
        lower = text.lower()
        if lower == text:
            return [text]
        return [text, lower]

    @classmethod
    def _find_value_in_line(
        cls,
        line: str,
        *,
        input_value: JSONValue,
        field_key: str | None = None,
        search_from: int = 0,
    ) -> "CaretSpan | None":
        candidates = cls._build_value_candidates(input_value)
        if field_key is not None:
            key_marker = f'"{field_key}":'
            key_pos = line.find(key_marker)
            if key_pos != -1:
                after_key = key_pos + len(key_marker)
                for candidate in candidates:
                    pos = line.find(candidate, after_key)
                    if pos != -1:
                        return CaretSpan(start=pos, end=pos + len(candidate))
        for candidate in candidates:
            pos = line.rfind(candidate, search_from)
            if pos != -1:
                return CaretSpan(start=pos, end=pos + len(candidate))
        return None

    @classmethod
    def _nonwhitespace_span(cls, line: str) -> "CaretSpan":
        stripped = line.lstrip()
        if not stripped:
            return CaretSpan(start=0, end=0)
        pos = len(line) - len(stripped)
        return CaretSpan(start=pos, end=len(line))

    @classmethod
    def _caret_for_key_line(cls, line: str) -> "CaretSpan":
        sep_pos = max(line.rfind(":"), line.rfind("="))
        if sep_pos != -1:
            after = sep_pos + 1
            while after < len(line) and line[after] == " ":
                after += 1
            if after < len(line):
                return CaretSpan(start=after, end=len(line))
        return cls._nonwhitespace_span(line)

    @classmethod
    def _caret_after_equals(cls, line: str) -> "CaretSpan":
        eq_pos = line.find("=")
        if eq_pos != -1:
            return CaretSpan(start=eq_pos + 1, end=len(line))
        return CaretSpan(start=0, end=len(line))

    @classmethod
    def _compute_line_carets(
        cls,
        content_lines: list[str],
        *,
        input_value: JSONValue,
        field_key: str | None,
    ) -> "list[CaretSpan]":
        if len(content_lines) == 1:
            if input_value is None:
                return [cls._caret_after_equals(content_lines[0])]
            found = cls._find_value_in_line(
                content_lines[0],
                input_value=input_value,
                field_key=field_key,
            )
            return [found if found is not None else CaretSpan(start=0, end=0)]
        result: list[CaretSpan] = [cls._caret_for_key_line(content_lines[0])]
        result.extend(cls._nonwhitespace_span(line) for line in content_lines[1:])
        return result

    def resolve_location(
        self,
        *,
        field_path: list[str],
        file_content: str | None,
        nested_conflict: NestedConflict | None,  # noqa: ARG002
        input_value: JSONValue = None,
    ) -> list[SourceLocation]:
        file_path = self.file_path_for_errors()
        if file_content is None or not field_path:
            return [self._empty_location(self.location_label, file_path)]

        if self.path_finder_class is None:
            return [self._empty_location(self.location_label, file_path)]

        search_path = self._build_search_path(field_path, self.prefix)
        finder = self.path_finder_class(file_content)
        line_range = finder.find_line_range(search_path)
        if line_range is None:
            line_range = self._find_parent_line_range(finder, search_path)
        if line_range is None:
            return [self._empty_location(self.location_label, file_path)]

        lines = file_content.splitlines()
        content_lines: list[str] | None = None
        line_carets: list[CaretSpan] | None = None
        if 0 < line_range.start <= len(lines):
            end = min(line_range.end, len(lines))
            raw = lines[line_range.start - 1 : end]
            content_lines = self._strip_common_indent(raw)
            field_key = field_path[-1] if field_path else None
            line_carets = self._compute_line_carets(
                content_lines,
                input_value=input_value,
                field_key=field_key,
            )

        return [
            SourceLocation(
                location_label=self.location_label,
                file_path=file_path,
                line_range=line_range,
                line_content=content_lines,
                env_var_name=None,
                line_carets=line_carets,
            ),
        ]


# --8<-- [start:file-source]
@dataclass(kw_only=True, repr=False)
class FileFieldMixin:
    file: "FileLike | FilePath | None" = None
    search_system_paths: bool | None = None
    system_config_dirs: "SystemConfigDirsArg | None" = None
    # --8<-- [end:file-source]

    def __post_init__(self) -> None:
        if isinstance(self.file, (str, Path)):
            self.file = expand_file_path(str(self.file), mode="strict")

    @cached_property
    def _resolved_file_path(self) -> Path | None:
        """Resolve file path with optional system path search.

        Cached to avoid re-traversing system directories on repeated access
        """
        if self.file is None or isinstance(self.file, FILE_LIKE_TYPES):
            return None

        file_path = self.file if isinstance(self.file, Path) else Path(self.file)
        if file_path.exists():
            return file_path

        if self.search_system_paths:
            return find_config(file_path.name, self.system_config_dirs)

        return None

    @staticmethod
    def resolve_file_field(file: "FileLike | FilePath | None") -> FileOrStream:
        if isinstance(file, FILE_LIKE_TYPES):
            return file
        if file is not None:
            return Path(file)
        return Path()

    @staticmethod
    def file_field_display(file: "FileLike | FilePath | None") -> str | None:
        if isinstance(file, FILE_LIKE_TYPES):
            return "<stream>"
        if file is not None:
            return str(file)
        return None

    @staticmethod
    def file_field_path_for_errors(file: "FileLike | FilePath | None") -> Path | None:
        if isinstance(file, FILE_LIKE_TYPES):
            return None
        if file is not None:
            return Path(file)
        return None

    def file_display(self) -> str | None:
        if self._resolved_file_path is not None:
            return str(self._resolved_file_path)
        return self.file_field_display(self.file)

    def file_path_for_errors(self) -> Path | None:
        if self._resolved_file_path is not None:
            return self._resolved_file_path
        return self.file_field_path_for_errors(self.file)


@dataclass(kw_only=True, repr=False)
class FileSource(FileFieldMixin, Source, abc.ABC):
    location_label: ClassVar[str] = "FILE"

    def __repr__(self) -> str:
        display = self.format_name
        file_path_display = self.file_display()
        if file_path_display is not None:
            return f"{display} '{file_path_display}'"
        return display

    def _load(self) -> JSONValue:
        if isinstance(self.file, FILE_LIKE_TYPES):
            return self._load_file(self.file)

        path = self._resolved_file_path
        if path is None:
            msg = f"Config file not found: {self.file}"
            raise FileNotFoundError(msg)

        return self._load_file(path)

    @abc.abstractmethod
    def _load_file(self, path: FileOrStream) -> JSONValue: ...


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

    def _resolve_field_strategy(
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

    def additional_loaders(self) -> "list[Provider]":
        return string_value_loaders()

    @staticmethod
    def _resolve_var_name(
        field_path: list[str],
        prefix: str | None,
        nested_sep: str,
        conflict: NestedConflict | None,
    ) -> str:
        def _build_name(parts: list[str]) -> str:
            var_name = nested_sep.join(part.upper() for part in parts)
            if prefix is not None:
                return prefix + var_name
            return var_name

        json_var = _build_name(field_path[:1])
        if conflict is not None and conflict.used_var == json_var:
            return json_var
        return _build_name(field_path)

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
            strategy = self._resolve_field_strategy(
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
            strategy = self._resolve_field_strategy(
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
