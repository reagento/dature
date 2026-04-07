import io
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, cast

from dature.errors import LineRange, SourceLocation
from dature.sources.base import FileFieldMixin, FlatKeySource
from dature.types import (
    BINARY_IO_TYPES,
    TEXT_IO_TYPES,
    JSONValue,
    NestedConflict,
    NestedConflicts,
    NestedResolve,
    NestedResolveStrategy,
)


@dataclass(kw_only=True, repr=False)
class EnvSource(FlatKeySource):
    format_name = "env"
    location_label: ClassVar[str] = "ENV"

    def _load(self) -> JSONValue:
        return cast("JSONValue", os.environ)

    @classmethod
    def resolve_location(
        cls,
        *,
        field_path: list[str],
        file_path: Path | None,  # noqa: ARG003
        file_content: str | None,  # noqa: ARG003
        prefix: str | None,
        nested_conflict: NestedConflict | None,
        split_symbols: str | None = None,
    ) -> list[SourceLocation]:
        resolved_symbols = split_symbols or "__"
        var_name = cls._resolve_var_name(field_path, prefix, resolved_symbols, nested_conflict)
        env_var_value: str | None = None
        if nested_conflict is not None:
            json_var = cls._resolve_var_name(field_path[:1], prefix, resolved_symbols, None)
            if nested_conflict.used_var == json_var:
                env_var_value = nested_conflict.json_raw_value
        return [
            SourceLocation(
                location_label=cls.location_label,
                file_path=None,
                line_range=None,
                line_content=None,
                env_var_name=var_name,
                env_var_value=env_var_value,
            ),
        ]

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
        if self.prefix and not key.startswith(self.prefix):
            return

        processed_key = key[len(self.prefix) :] if self.prefix else key
        processed_key = processed_key.lower()

        parts = processed_key.split(self.split_symbols)
        self._process_key_value(
            parts=parts,
            value=value,
            result=result,
            conflicts=conflicts,
            resolved_nested_strategy=resolved_nested_strategy,
            resolved_nested_resolve=resolved_nested_resolve,
        )


@dataclass(kw_only=True, repr=False)
class EnvFileSource(FileFieldMixin, EnvSource):
    format_name = "envfile"
    location_label: ClassVar[str] = "ENV FILE"

    def __post_init__(self) -> None:
        self._init_file_field()

    def __repr__(self) -> str:
        display = self.format_name
        file_path_display = self.file_display()
        if file_path_display is not None:
            return f"{display} '{file_path_display}'"
        return display

    @classmethod
    def resolve_location(
        cls,
        *,
        field_path: list[str],
        file_path: Path | None,
        file_content: str | None,
        prefix: str | None,
        nested_conflict: NestedConflict | None,
        split_symbols: str | None = None,
    ) -> list[SourceLocation]:
        resolved_symbols = split_symbols or "__"
        var_name = cls._resolve_var_name(field_path, prefix, resolved_symbols, nested_conflict)
        line_range: LineRange | None = None
        line_content: list[str] | None = None
        if file_content is not None:
            line_range, line_content = _find_env_line(file_content, var_name)
        return [
            SourceLocation(
                location_label=cls.location_label,
                file_path=file_path,
                line_range=line_range,
                line_content=line_content,
                env_var_name=var_name,
            ),
        ]

    def _load(self) -> JSONValue:
        """Parse .env file into a flat key=value dict (before nesting/expand/parse)."""
        path = self.resolve_file_field(self.file)
        raw_pairs: dict[str, JSONValue] = {}

        if isinstance(path, TEXT_IO_TYPES):
            self._collect_pairs(path, raw_pairs)
        elif isinstance(path, BINARY_IO_TYPES):
            wrapper = io.TextIOWrapper(cast("io.BufferedReader", path))
            self._collect_pairs(wrapper, raw_pairs)
        else:
            with path.open() as f:
                self._collect_pairs(f, raw_pairs)

        return raw_pairs

    @staticmethod
    def _collect_pairs(
        lines: Iterable[str],
        pairs: dict[str, JSONValue],
    ) -> None:
        for raw_line in lines:
            if not (line := raw_line.strip()) or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            _min_quoted_len = 2
            if len(value) >= _min_quoted_len and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            pairs[key] = value


def _find_env_line(content: str, var_name: str) -> tuple[LineRange | None, list[str] | None]:
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key == var_name:
            return LineRange(start=i, end=i), [stripped]
    return None, None
