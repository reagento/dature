"""Core ``Source`` ABC plus utilities shared across all source types.

Owns the ``Source`` abstract base class, ``string_value_loaders``, and
``clone_source``. File-based, flat-key, and remote subclasses live in
``file_source``, ``flat_key``, and ``remote`` respectively. Caret / line-range
rendering helpers live in ``presentation``.
"""

import abc
import contextlib
import copy
import json
import logging
from collections.abc import Iterable
from dataclasses import MISSING, dataclass, field, fields
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, ClassVar, cast

from adaptix import Retort, loader
from adaptix.provider import Provider

from dature.conditions import Condition
from dature.errors import CaretSpan, LineRange, SourceLocation
from dature.expansion.env_expand import expand_env_vars
from dature.field_path import FieldPath
from dature.loaders import (
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
from dature.sources.presentation import (
    build_search_path,
    empty_location,
    find_parent_line_range,
    strip_common_indent,
)
from dature.sources.presentation import (
    compute_line_carets as _compute_line_carets,
)
from dature.types import (
    DotSeparatedPath,
    ExpandEnvVarsMode,
    FieldMapping,
    JSONValue,
    LoadRawResult,
    NameStyle,
    NestedConflict,
    TypeLoaderMap,
)
from dature.validators.root import RootPredicate
from dature.validators.types import FieldValidators

logger = logging.getLogger("dature")


def string_value_loaders() -> list[Provider]:
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


# --8<-- [start:load-metadata]
@dataclass(kw_only=True, repr=False)
class Source(abc.ABC):
    prefix: "DotSeparatedPath | None" = None
    name_style: "NameStyle | None" = None
    field_mapping: "FieldMapping | None" = None
    root_validators: "Iterable[RootPredicate] | None" = None
    validators: "FieldValidators | None" = None
    expand_env_vars: "ExpandEnvVarsMode | None" = None
    skip_if_broken: bool | None = None
    skip_field_if_invalid: "bool | tuple[FieldPath, ...] | None" = None
    type_loaders: "TypeLoaderMap | None" = None
    tag: str | None = None
    when: "Condition | None" = None

    format_name: ClassVar[str]
    location_label: ClassVar[str]
    config_group: ClassVar[str | None] = None

    retorts: "dict[Any, Retort]" = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    # --8<-- [end:load-metadata]
    def __post_init__(self) -> None:
        if self.when is not None and not isinstance(self.when, Condition):
            msg = (
                f"when= must be a Condition built with the When() DSL, "
                f"got {type(self.when).__name__!r}. "
                'Example: when=When("${APP_ENV}") == "prod"'
            )
            raise TypeError(msg)

    def __repr__(self) -> str:
        parts = []
        for f in fields(self):
            if not f.init or not f.repr:
                continue
            value = getattr(self, f.name, MISSING)
            if value is MISSING:
                continue
            if f.default is not MISSING and value == f.default:
                continue
            if f.default_factory is not MISSING:
                with contextlib.suppress(Exception):
                    if value == f.default_factory():
                        continue
            parts.append(f"{f.name}={value!r}")
        return f"{type(self).__name__}({', '.join(parts)})"

    @property
    def resolved_tag(self) -> str:
        """Tag used to identify this source in ${@tag.key} cross-refs.

        Defaults to format_name when tag is not set explicitly.
        """
        return self.tag if self.tag is not None else self.format_name

    def file_display(self) -> str | None:
        return None

    def file_path_for_errors(self) -> Path | None:
        return None

    def encoding_for_errors(self) -> str | None:
        return None

    def display_name(self) -> str:
        return self.file_display() or self.format_name

    def _alias_to_field_name(self, raw_key: str) -> str | None:
        """Return the dataclass field name if *raw_key* is a field_mapping alias, else None."""
        if not self.field_mapping:
            return None
        for field_path, aliases in self.field_mapping.items():
            if not isinstance(field_path, FieldPath):
                continue
            alias_list = (aliases,) if isinstance(aliases, str) else aliases
            if raw_key in alias_list and field_path.parts:
                return field_path.parts[-1]
        return None

    def additional_loaders(self) -> "list[Provider]":
        return []

    def validate(self) -> None:
        """Hook called lazily inside ``LoadCtx.load`` after cross-ref interpolation.

        Default no-op. Subclasses with ``config_group`` set may override to
        check post-merge invariants (required fields, mutually exclusive
        options, etc.) — by the time this runs, all None instance fields
        have been populated from ``dature.config.<config_group>`` and any
        ``${@tag.key}`` refs in init-fields have been resolved.
        """
        return

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

    def build_line_index(self, content: str) -> "dict[tuple[str, ...], LineRange] | None":  # noqa: ARG002
        """Return a mapping from field-path tuples to line ranges within *content*.

        Part of the error-location protocol: called by the errors layer to resolve
        field positions in file content. Override in FileSource subclasses that support
        line-number error reporting. Return ``None`` to opt out (default).
        """
        return None

    def compute_line_carets(
        self,
        content_lines: list[str],
        *,
        input_value: JSONValue,
        field_key: str | None,
    ) -> "list[CaretSpan]":
        """Compute caret spans for *content_lines* pointing at *input_value*.

        Part of the error-location protocol: called by the errors layer when masking
        is applied to already-extracted line content. The default implementation works
        for most text formats; override for special caret placement logic.
        """
        return _compute_line_carets(content_lines, input_value=input_value, field_key=field_key)

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
            return [empty_location(self.location_label, file_path)]

        search_path = build_search_path(field_path, self.prefix)
        line_index = self.build_line_index(file_content)
        if line_index is None:
            return [empty_location(self.location_label, file_path)]

        line_range = line_index.get(tuple(search_path))
        if line_range is None:
            line_range = find_parent_line_range(line_index, search_path)
        if line_range is None:
            return [empty_location(self.location_label, file_path)]

        lines = file_content.splitlines()
        content_lines: list[str] | None = None
        line_carets: list[CaretSpan] | None = None
        if 0 < line_range.start <= len(lines):
            end = min(line_range.end, len(lines))
            raw = lines[line_range.start - 1 : end]
            content_lines = strip_common_indent(raw)
            field_key = field_path[-1] if field_path else None
            line_carets = self.compute_line_carets(
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


def clone_source[T: Source](source: T, overrides: dict[str, object]) -> T:
    """Return a shallow copy of *source* with *overrides* applied.

    Drops the cached ``_resolved_file_path`` so it re-resolves against
    the overridden fields instead of returning a stale result.
    """
    new = copy.copy(source)
    vars(new).update(overrides)
    vars(new).pop("_resolved_file_path", None)
    return new
